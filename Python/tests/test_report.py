"""run.py: graph after a successful delivery of the built-in mission."""

import math
import sys
import threading
import time
from pathlib import Path

from RSMA.MockServer import MockServer
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP.Topics import Float32, MissionStatus, Pose, SwarmTelemetry
from scene.flight_report import FlightRecorder

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402

PHASES = [("Натяжение тросов", 0.4), ("Подъём груза", 0.6), ("Перенос груза", 1.0), ("Выгрузка", 0.5),
          ("Подъём порожняком", 1.0)]


def fake_mission(server: MockServer, stop: threading.Event, speedup: float = 1.0):
    """Built-in mission of scene 1 as RSMA publishes it: base (115, 85) -> pad (75, 45)."""
    base, pad = Vector3(115, 1.0, 85), Vector3(75, 1.0, 45)
    ts = 1
    mission_t = 0.0
    for phase, duration in PHASES:
        t0 = time.monotonic()
        while time.monotonic() - t0 < duration and not stop.is_set():
            k = (time.monotonic() - t0) / duration
            if phase == "Натяжение тросов":
                p = base
            elif phase == "Подъём груза":
                p = Vector3(base.x, 1.0 + 12 * k, base.z)
            elif phase == "Перенос груза":
                p = base.lerp(pad, k) + Vector3(0, 12, 0)
            elif phase == "Выгрузка":
                p = Vector3(pad.x, 13.0 - 12 * k, pad.z)
            else:
                p = pad
            ts += 1
            mission_t += 0.02 * 20  # "simulation" runs 20x faster than the test
            swing = 4.0 * math.sin(mission_t / 3.0) if phase == "Перенос груза" else 0.5
            server.broker.publish_obj("PayloadPose", Pose(position=p, timestamp=ts))
            server.broker.publish_obj("SwarmTelemetry", SwarmTelemetry(
                timestamp=ts, missionTime=mission_t, swingAngle=abs(swing), totalTension=120.0, minTension=18.0,
                maxTension=22.0, payloadSpeed=4.0 if phase == "Перенос груза" else 1.0, payloadAttached=True))
            dist = math.hypot(pad.x - p.x, pad.z - p.z)
            server.broker.publish_obj("MissionStatus", MissionStatus(ts, phase, 1 - dist / 56.6, dist, p, pad))
            for i in range(1, 7):
                server.broker.publish_obj(f"CableForce_{i}", Float32(value=20.0 if phase != "Подъём порожняком" else 0.0,
                                                                     timestamp=ts))
            time.sleep(0.02)


def test_recorder_detects_delivery_after_unload():
    r = FlightRecorder()
    for t, phase in enumerate(["Подъём груза", "Перенос груза", "Выгрузка", "Выгрузка"]):
        r.add(float(t), phase, Vector3(0, 1, 0), 1.0, 100.0)
        assert not r.delivered
    r.add(4.0, "Подъём порожняком", Vector3(0, 1, 0), 0.0, 0.0)
    assert r.delivered and r.delivered_at == 4.0


def test_report_after_delivery(tmp_path, capsys):
    with MockServer(port=0, host="127.0.0.1") as server:
        stop = threading.Event()
        threading.Thread(target=fake_mission, args=(server, stop), daemon=True).start()
        recorder = run.monitor("127.0.0.1", server.port, duration=20, plot=True, log_dir=tmp_path, show=False,
                               parameters={"delivery": {"cruiseSpeed": 4.0}})
        stop.set()
    assert recorder.delivered
    pngs, csvs = list(tmp_path.glob("delivery_*.png")), list(tmp_path.glob("delivery_*.csv"))
    assert len(pngs) == 1 and len(csvs) == 1 and pngs[0].stat().st_size > 10_000
    info = recorder.summary()
    assert 50 < info["path"] < 65  # 56.6 m leg
    assert 2.0 < info["max_swing"] <= 4.0
    assert info["time"] > 30  # mission (simulation) time, not wall-clock
    assert "Груз доставлен" in capsys.readouterr().out
