import subprocess
import sys
from pathlib import Path

import pytest

from RSMA.uDTP.Topics import CameraFramePacket
from scene import Simulation, Vector3

SCRIPTS = Path(__file__).resolve().parent.parent / "Scripts"


@pytest.fixture
def sim():
    with Simulation.offline() as s:
        yield s


def test_scene_contents(sim):
    assert sim.find_drones() == [1, 2, 3, 4, 5, 6]
    assert sim.payload_pose().position == Vector3(0.0, 0.25, 0.0)
    assert sim.cable_force(1) == 0.0  # drones stand next to the payload, cables slack
    assert len(sim.drones()) == 6


def test_swarm_delivers_payload(sim):
    swarm = sim.swarm()
    assert swarm.ground_y == pytest.approx(0.25)
    assert swarm.lift(3.0)
    assert swarm.payload_position.y > 2.8
    assert all(f > 10 for f in swarm.cable_forces().values())  # payload hangs on all cables
    assert swarm.move_payload_by(6, 0, 3)
    assert swarm.lower()
    assert swarm.land()
    p = swarm.payload_position
    assert p.x == pytest.approx(6, abs=0.15) and p.z == pytest.approx(3, abs=0.15)
    assert p.y == pytest.approx(0.25, abs=0.05)


def test_swarm_keeps_formation(sim):
    swarm = sim.swarm()
    swarm.lift(2.0)
    swarm.move_payload_by(4, 0, 0)
    payload = swarm.payload_position
    for d in swarm.drones:
        ox, oz = swarm.offsets[d.id]
        assert d.position.x - payload.x == pytest.approx(ox, abs=0.3)
        assert d.position.z - payload.z == pytest.approx(oz, abs=0.3)


def test_swarm_needs_payload():
    with Simulation.offline() as sim:
        sim.scene.physics.broker._states.clear()
        with pytest.raises(RuntimeError):
            sim.swarm()


def test_single_drone_api(sim):
    drone = sim.drone(1)
    start = drone.position
    assert drone.move_by(0, 1.0, 0, tolerance=0.2)
    assert drone.position.y == pytest.approx(start.y + 1.0, abs=0.2)
    assert drone.set_target(0, 0, 0) == Vector3(0.0, 0.01, 0.0)
    assert sim.drone(42).position is None
    with pytest.raises(RuntimeError):
        sim.drone(42).move_by(1, 0, 0)


def test_camera_frame_is_flipped(sim):
    pixels = bytes([1, 1, 1, 2, 2, 2])  # 1x2 image, bottom row first
    sim.client.broker.publish_obj("Camera_0", CameraFramePacket(1, 2, 3, 5, 1, pixels))
    frame = sim.camera(0).frame()
    assert frame.shape == (2, 1, 3)
    assert frame[0, 0, 0] == 2 and frame[1, 0, 0] == 1
    assert sim.camera(1).frame() is None


@pytest.mark.parametrize("script", sorted(p.name for p in SCRIPTS.glob("0*.py")))
def test_example_scripts_run_offline(script):
    result = subprocess.run([sys.executable, str(SCRIPTS / script), "--offline"],
                            capture_output=True, text=True, timeout=300)
    if script.startswith("04_"):  # no camera in the offline scene
        assert "Нет кадров" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


def test_console_starts_offline():
    result = subprocess.run([sys.executable, "-m", "scene", "--offline"],
                            input="print(len(swarm.drones), swarm.payload_position)\n",
                            capture_output=True, text=True, timeout=60,
                            cwd=Path(__file__).resolve().parent.parent / "Source")
    assert result.returncode == 0, result.stderr
    assert "6 Vector3(x=0.0, y=0.25, z=0.0)" in result.stdout
