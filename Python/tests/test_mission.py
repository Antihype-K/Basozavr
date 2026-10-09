"""End-to-end: controller + physics model of the scene, no Unity."""

import numpy as np
import pandas as pd
import pytest

from control.flight_state_machine import SwarmFlightPhase
from control.swarm_controller import SwarmRSMAController
from RSMA.Broker import InMemoryBroker, LocalClient
from RSMA.Client import RSMAClient
from RSMA.MockServer import MockServer
from sim.swarm_sim import SwarmPhysicsSim


def run_mission(cfg, wind=None, start=(2.0, 3.0, 0.25), csv_log=False):
    broker = InMemoryBroker()
    ctrl = SwarmRSMAController(client=LocalClient(broker), config=cfg, csv_log=csv_log)
    sim = SwarmPhysicsSim.around_payload(broker, list(start), ctrl.offsets, wind=wind)
    stats = {"radius": [], "swing": []}

    def before_step(dt):
        sim.step(dt)
        if ctrl.fsm is not None and ctrl.fsm.phase == SwarmFlightPhase.TRAJECTORY:
            xy = np.array([sim.drone_pos[i][:2] for i in sim.ids])
            stats["radius"].append(np.mean(np.linalg.norm(xy - sim.payload_pos[:2], axis=1)))
            stats["swing"].append(np.linalg.norm(xy.mean(axis=0) - sim.payload_pos[:2]))

    phase = ctrl.run(realtime=False, max_steps=20_000, before_step=before_step)
    return ctrl, sim, phase, stats


def test_mission_delivers_payload(cfg):
    ctrl, sim, phase, stats = run_mission(cfg)
    assert phase == SwarmFlightPhase.FINISHED
    np.testing.assert_allclose(sim.payload_pos[:2], ctrl.fsm.finish_xy, atol=0.1)
    assert sim.payload_pos[2] == pytest.approx(sim.payload.ground_z)
    # formation keeps its radius while carrying the load
    assert np.mean(stats["radius"]) > 0.8 * cfg.FORMATION_RADIUS


def test_anti_sway_reduces_swing_in_wind(cfg):
    wind = np.array([15.0, 0.0, 0.0])
    cfg.USE_ANTI_SWAY = False
    *_, off = run_mission(cfg, wind=wind)
    cfg.USE_ANTI_SWAY = True
    *_, on = run_mission(cfg, wind=wind)
    assert np.mean(on["swing"]) < np.mean(off["swing"])
    assert np.mean(on["radius"]) > 0.8 * cfg.FORMATION_RADIUS


def test_mission_writes_csv_log(cfg, tmp_path):
    cfg.LOG_DIR = str(tmp_path)
    ctrl, *_ = run_mission(cfg, csv_log=True)
    logs = list(tmp_path.glob("flight_log_*.csv"))
    assert len(logs) == 1
    df = pd.read_csv(logs[0])
    assert len(df) == ctrl.step_count
    assert df["phase"].iloc[-1] == SwarmFlightPhase.FINISHED
    assert {"drone_6_z", "cable_force_6"} <= set(df.columns)

    import visualize

    out = tmp_path / "dashboard.png"
    assert visualize.main([str(logs[0]), "--save", str(out)]) == 0
    assert out.stat().st_size > 0


def test_controller_over_real_socket(cfg):
    """A few steps through RSMAClient <-> MockServer (same protocol as Unity NetMQServer)."""
    with MockServer(port=0, host="127.0.0.1") as server:
        sim = SwarmPhysicsSim.around_payload(server.broker, [0, 0, 0.25],
                                             SwarmRSMAController(client=LocalClient(), config=cfg,
                                                                 csv_log=False).offsets)
        with RSMAClient(host="127.0.0.1", port=server.port, timeout=2000) as client:
            ctrl = SwarmRSMAController(client=client, config=cfg, csv_log=False)
            ctrl.run(realtime=False, max_steps=50, before_step=sim.step, payload_timeout=2.0)
            assert ctrl.step_count == 50
            assert ctrl.fsm.phase == SwarmFlightPhase.LIFT
            assert sim.drone_target[1] is not None


def test_run_without_payload_times_out(cfg):
    ctrl = SwarmRSMAController(client=LocalClient(), config=cfg, csv_log=False)
    assert ctrl.run(realtime=False, payload_timeout=0.05) is None


def test_mission_pauses_while_telemetry_is_frozen(cfg):
    """Unity paused for 3 s mid-flight: the trajectory must not run away meanwhile."""
    broker = InMemoryBroker()
    ctrl = SwarmRSMAController(client=LocalClient(broker), config=cfg, csv_log=False)
    sim = SwarmPhysicsSim.around_payload(broker, [0, 0, 0.25], ctrl.offsets)
    ctrl.start_mission(ctrl.read_payload_position())

    while ctrl.fsm.phase != SwarmFlightPhase.TRAJECTORY:
        sim.step(cfg.DT)
        ctrl.step(cfg.DT)
    for _ in range(300):
        sim.step(cfg.DT)
        ctrl.step(cfg.DT)
    progress = ctrl.traj.s

    for _ in range(300):  # sim frozen, controller keeps ticking
        ctrl.step(cfg.DT)
    assert ctrl.telemetry_stale
    assert ctrl.traj.s - progress < (cfg.TELEMETRY_TIMEOUT + 0.05) * cfg.V_MAX

    frozen_at = ctrl.traj.s
    for _ in range(10):
        sim.step(cfg.DT)
        ctrl.step(cfg.DT)
    assert not ctrl.telemetry_stale
    assert ctrl.traj.s > frozen_at

    for _ in range(20_000):
        sim.step(cfg.DT)
        if ctrl.step(cfg.DT) == SwarmFlightPhase.FINISHED:
            break
    assert ctrl.fsm.is_finished
    np.testing.assert_allclose(sim.payload_pos[:2], ctrl.fsm.finish_xy, atol=0.1)


def test_mission_status_is_published_for_rsma_hud(cfg):
    """SwarmLiveView in scene 1 shows the MissionStatus topic."""
    from RSMA.uDTP.Topics import MissionStatus

    ctrl, sim, phase, _ = run_mission(cfg)
    status = sim.broker.get_obj("MissionStatus", MissionStatus)
    assert status.phase == SwarmFlightPhase.FINISHED
    assert status.progress == pytest.approx(1.0, abs=0.02)
    assert status.distanceToFinish < 0.2
    # Unity coordinates: Python (x, y, z) -> Unity (x, z, y)
    assert status.finish.x == pytest.approx(ctrl.fsm.finish_xy[0])
    assert status.finish.z == pytest.approx(ctrl.fsm.finish_xy[1])


def test_altitudes_are_relative_to_start(cfg):
    """Scene 1 base stands on terrain: cruise/land heights are measured from the payload start."""
    ctrl, sim, phase, _ = run_mission(cfg, start=(2.0, 3.0, 7.25))
    assert phase == SwarmFlightPhase.FINISHED
    assert ctrl.fsm.target_flight_z == pytest.approx(7.25 + cfg.CRUISE_ALTITUDE)
