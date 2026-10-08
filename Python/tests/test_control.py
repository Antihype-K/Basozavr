import numpy as np
import pytest

from control.anti_sway import AntiSwayController
from control.flight_state_machine import FlightStateMachine, SwarmFlightPhase
from control.formation import FormationManager
from control.trajectory import JerkLimitedTrajectory

DT = 0.01


# --- Trajectory ---

@pytest.mark.parametrize("length, v_max", [(21.5, 0.8), (5.0, 2.0), (0.3, 0.8), (0.001, 1.0)])
def test_trajectory_respects_limits_and_ends_at_target(length, v_max):
    a_max, j_max = 1.0, 2.0
    traj = JerkLimitedTrajectory([0, 0, 3], [length * 0.6, length * 0.8, 3], v_max=v_max, a_max=a_max, j_max=j_max)
    prev_a, prev_s, steps = 0.0, 0.0, 0
    while not traj.is_finished:
        pos = traj.update(DT)
        steps += 1
        assert steps < 100_000
        assert abs(traj.v) <= v_max + 1e-9
        assert abs(traj.a) <= a_max + 1e-9
        assert abs(traj.a - prev_a) / DT <= j_max + 1e-6
        assert traj.s >= prev_s - 1e-12, "set point must never move backwards"
        assert traj.s <= traj.length + 1e-12, "no overshoot"
        prev_a, prev_s = traj.a, traj.s
    np.testing.assert_allclose(pos, [length * 0.6, length * 0.8, 3])
    assert steps * DT == pytest.approx(traj.duration, abs=DT)


def test_trajectory_zero_length_is_finished():
    traj = JerkLimitedTrajectory([1, 2, 3], [1, 2, 3])
    assert traj.is_finished
    np.testing.assert_allclose(traj.update(DT), [1, 2, 3])


def test_trajectory_rejects_bad_limits():
    with pytest.raises(ValueError):
        JerkLimitedTrajectory([0, 0, 0], [1, 0, 0], v_max=0)


# --- Formation ---

def test_formation_is_regular_polygon():
    offsets = FormationManager(6, radius=2.0).get_formation_offsets()
    assert sorted(offsets) == [1, 2, 3, 4, 5, 6]
    for off in offsets.values():
        assert np.linalg.norm(off[:2]) == pytest.approx(2.0)
    np.testing.assert_allclose(sum(offsets.values()), 0, atol=1e-12)


# --- Anti-sway ---

def test_anti_sway_ignores_nominal_formation_geometry():
    """A drone hanging at its formation offset is not a swing: no correction."""
    ctrl = AntiSwayController(k_sway=1.5, d_sway=0.5)
    offset = np.array([1.414, 0.0, 0.0])
    payload = np.array([0.0, 0.0, 3.0])
    drone = payload + offset + np.array([0, 0, 1.4])
    for _ in range(3):
        np.testing.assert_allclose(ctrl.compute_sway_correction(drone, payload, DT, nominal_offset=offset), 0)


def test_anti_sway_moves_drone_towards_swinging_payload():
    ctrl = AntiSwayController(k_sway=1.5, d_sway=0.0)
    drone = np.array([0.0, 0.0, 5.0])
    payload = np.array([-0.3, 0.2, 3.0])  # load swung back in X and sideways in Y
    corr = ctrl.compute_sway_correction(drone, payload, DT)
    assert corr[0] < 0 and corr[1] > 0


def test_anti_sway_first_step_has_no_derivative_kick():
    ctrl = AntiSwayController(k_sway=0.0, d_sway=1.0)
    corr = ctrl.compute_sway_correction(np.array([0, 0, 5.0]), np.array([0.5, 0, 3.0]), DT)
    np.testing.assert_allclose(corr, 0)


def test_anti_sway_correction_is_limited():
    ctrl = AntiSwayController(k_sway=100.0, d_sway=0.0, max_correction=0.5)
    corr = ctrl.compute_sway_correction(np.array([0, 0, 5.0]), np.array([1.0, 1.0, 3.0]), DT)
    assert np.linalg.norm(corr) == pytest.approx(0.5)


def test_anti_sway_degenerate_geometry():
    ctrl = AntiSwayController()
    np.testing.assert_allclose(ctrl.compute_sway_correction(np.zeros(3), np.zeros(3), DT), 0)


# --- FSM ---

class _InstantTrajectory:
    is_finished = False

    def __init__(self, target):
        self.target = np.asarray(target, dtype=float)

    def update(self, dt):
        self.is_finished = True
        return self.target


def make_fsm(**kw):
    params = dict(start_pos=[0, 0, 0.25], finish_xy=[10, 0], target_flight_z=3.0, target_land_z=0.5,
                  climb_rate=1.0, hang_height=1.5, drone_land_z=0.25, hover_time=2.0)
    params.update(kw)
    return FlightStateMachine(**params)


def test_fsm_full_mission_sequence():
    fsm = make_fsm()
    traj = _InstantTrajectory([10, 0, 3])
    payload_z = 0.25
    seen = []
    for _ in range(10_000):
        if fsm.phase in (SwarmFlightPhase.LIFT, SwarmFlightPhase.LAND):
            payload_z = fsm.current_cmd_z  # perfect tracking
        fsm.update(payload_z, DT, traj)
        if not seen or seen[-1] != fsm.phase:
            seen.append(fsm.phase)
        if fsm.is_finished:
            break
    assert seen == ["LIFT", "TRAJECTORY", "HOVER", "LAND", "LAND_DRONES", "FINISHED"]
    assert fsm.target_drone_z == pytest.approx(0.25)


def test_fsm_lift_threshold_follows_cruise_altitude():
    fsm = make_fsm(target_flight_z=4.5, lift_tolerance=0.35)
    fsm.update(2.7, DT, None)  # old hardcoded threshold was 2.65
    assert fsm.phase == SwarmFlightPhase.LIFT
    fsm.update(4.2, DT, None)
    assert fsm.phase == SwarmFlightPhase.TRAJECTORY


def test_fsm_hover_uses_simulation_time():
    fsm = make_fsm()
    fsm.phase = SwarmFlightPhase.HOVER
    for _ in range(199):
        fsm.update(3.0, DT, None)
    assert fsm.phase == SwarmFlightPhase.HOVER
    fsm.update(3.0, 0.02, None)
    assert fsm.phase == SwarmFlightPhase.LAND


def test_fsm_land_does_not_hang_on_tall_payload():
    """If the payload never gets below the threshold, drones still land after a settle time."""
    fsm = make_fsm(land_settle_time=1.0)
    fsm.phase = SwarmFlightPhase.LAND
    fsm.current_cmd_z = 3.0
    for _ in range(int((2.5 + 1.0) / DT) + 5):
        fsm.update(1.2, DT, None)
    assert fsm.phase == SwarmFlightPhase.LAND_DRONES


def test_fsm_drone_setpoint_is_rate_limited():
    fsm = make_fsm()
    fsm.update(0.25, DT, None)
    assert fsm.target_drone_z - 0.25 <= 2 * fsm.climb_rate * DT + 1e-9


class _NoFlagTrajectory:
    """Generator without is_finished: FSM falls back to the distance tolerance."""

    def __init__(self, points):
        self.points = list(points)

    def update(self, dt):
        return self.points.pop(0) if len(self.points) > 1 else self.points[0]


def test_fsm_waits_for_trajectory_completion():
    traj = JerkLimitedTrajectory([0, 0, 3], [10, 0, 3], v_max=1.0, a_max=1.0, j_max=2.0)
    fsm = make_fsm()
    fsm.phase = SwarmFlightPhase.TRAJECTORY
    prev = None
    while fsm.phase == SwarmFlightPhase.TRAJECTORY:
        center, _ = fsm.update(3.0, DT, traj)
        if prev is not None:
            # no set-point jump, including the step that switches to HOVER
            assert np.linalg.norm(center - prev) <= 1.0 * DT + 1e-9
        prev = center
    assert traj.is_finished
    np.testing.assert_allclose(prev, [10, 0])
    center, _ = fsm.update(3.0, DT, traj)
    assert np.linalg.norm(center - prev) < 1e-9


def test_fsm_distance_tolerance_for_generators_without_flag():
    fsm = make_fsm(finish_tolerance=0.3)
    fsm.phase = SwarmFlightPhase.TRAJECTORY
    traj = _NoFlagTrajectory([[9.0, 0, 3], [9.8, 0, 3]])
    fsm.update(3.0, DT, traj)
    assert fsm.phase == SwarmFlightPhase.TRAJECTORY
    fsm.update(3.0, DT, traj)
    assert fsm.phase == SwarmFlightPhase.HOVER
