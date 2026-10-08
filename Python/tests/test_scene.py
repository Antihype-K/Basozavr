import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from RSMA.Client import RSMAClient
from RSMA.MockServer import MockServer
from RSMA.uDTP.Topics import CameraFramePacket, ControlLease, MotorInput, RobotVelocity
from scene import Simulation, Vector3

SCRIPTS = Path(__file__).resolve().parent.parent / "Scripts"


@pytest.fixture
def sim():
    with Simulation.offline() as s:
        yield s


def lease(sim, robot="Maruz") -> ControlLease:
    return sim.client.get_state(f"ExternalControl_{robot}", ControlLease)


# --- Drone ---

def test_drone_fly_to_and_land(sim):
    drone = sim.drone(1)
    assert drone.position == Vector3(0.0, 0.1, 3.0)
    assert drone.fly_to(2, 5, 4, tolerance=0.3)
    assert drone.position.distance_to(Vector3(2, 5, 4)) <= 0.3
    assert drone.move_by(0, 0, 3)
    assert drone.land(ground_y=0.1, tolerance=0.05)
    assert drone.position.y == pytest.approx(0.1, abs=0.05)


def test_drone_zero_target_is_nudged(sim):
    assert sim.drone(1).set_target(0, 0, 0) == Vector3(0.0, 0.01, 0.0)


def test_drone_timeout(sim):
    assert not sim.drone(1).fly_to(100, 5, 0, timeout=0.5)


def test_missing_drone(sim):
    drone = sim.drone(42)
    assert drone.position is None
    with pytest.raises(RuntimeError):
        drone.move_by(1, 0, 0)


# --- Maruz ---

def test_maruz_drive_forward_and_turn_left(sim):
    maruz = sim.maruz()
    maruz.drive(0.5, duration=2.0)
    assert maruz.position.z == pytest.approx(1.0, abs=0.02)
    maruz.turn(math.pi / 4, duration=2.0)  # positive angular = left = yaw decreases
    assert maruz.heading == pytest.approx(-90.0, abs=1.0)
    cmd = sim.client.get_state("MaruzTargetVelocity", RobotVelocity)
    assert cmd.linearVelocity == 0 and cmd.angularVelocity == 0
    assert lease(sim).level == 1


def test_maruz_go_to_rotate_follow(sim):
    maruz = sim.maruz()
    assert maruz.go_to(3, 4, tolerance=0.3)
    assert math.hypot(maruz.position.x - 3, maruz.position.z - 4) <= 0.3
    assert maruz.rotate_to(90.0)
    assert maruz.heading == pytest.approx(90.0, abs=3.0)
    assert maruz.follow([(0, 0), (2, 0), (2, 2)])
    assert math.hypot(maruz.position.x - 2, maruz.position.z - 2) <= 0.35


def test_maruz_wheels_take_actuator_control(sim):
    maruz = sim.maruz()
    maruz.set_wheels(2.0, -0.5)
    assert lease(sim).level == 2
    assert sim.client.get_state("MaruzML", MotorInput).input == 1.0  # clamped
    maruz.set_wheels(0.1, 0.1, duration=1.0)
    assert maruz.position.z > 0.5
    maruz.release()
    assert lease(sim).level == 0


def test_close_releases_control():
    sim = Simulation.offline()
    sim.maruz().drive(0.3)
    broker = sim.client.broker
    sim.close()
    assert broker.get_obj("ExternalControl_Maruz", ControlLease).level == 0


def test_go_to_timeout(sim):
    assert not sim.maruz().go_to(100, 100, timeout=1.0)


# --- Sensors ---

def test_lidar_and_rangefinder(sim):
    lidar = sim.lidar()
    assert lidar.min_distance() == 20.0
    assert len(lidar.angles()) == 128
    assert lidar.points().shape == (0, 2)  # all rays at max range
    assert lidar.distance_at(90) == 20.0
    assert sim.rangefinder().distance() == 4.0
    assert sim.lidar("NoSuchTopic").scan() is None


def test_lidar_points_geometry(sim):
    sim.client.broker.publish_obj("Lidar", __import__("RSMA.uDTP.Topics", fromlist=["LaserScan128"]).LaserScan128(
        ranges=[1.0] + [20.0] * 127, angleMin=90.0, angleIncrement=1.0, rangeMax=20.0, timestamp=1))
    np.testing.assert_allclose(sim.lidar().points(), [[1.0, 0.0]], atol=1e-9)  # 90° = to the right (+x)


def test_camera_frame_is_flipped(sim):
    pixels = bytes([1, 1, 1, 2, 2, 2])  # 1x2 image, bottom row first
    sim.client.broker.publish_obj("Camera_0", CameraFramePacket(1, 2, 3, 5, 1, pixels))
    frame = sim.camera(0).frame()
    assert frame.shape == (2, 1, 3)
    assert frame[0, 0, 0] == 2 and frame[1, 0, 0] == 1
    assert sim.camera(1).frame() is None


def test_get_returns_none_for_unpublished(sim):
    assert sim.payload_pose() is None
    assert sim.cable_force(1) is None


# --- Online mode: background lease renewal ---

def test_keepalive_renews_lease_and_command():
    with MockServer(port=0, host="127.0.0.1") as server:
        client = RSMAClient(host="127.0.0.1", port=server.port, timeout=2000)
        sim = Simulation(client=client, keepalive_period=0.05)
        sim.maruz().drive(0.4, 0.1)
        first = server.broker.get_obj("ExternalControl_Maruz", ControlLease)
        server.broker.publish_obj("MaruzTargetVelocity", RobotVelocity(timestamp=1))  # Unity overwrote it
        time.sleep(0.3)
        renewed = server.broker.get_obj("ExternalControl_Maruz", ControlLease)
        assert renewed.timestamp > first.timestamp and renewed.level == 1
        assert server.broker.get_obj("MaruzTargetVelocity", RobotVelocity).linearVelocity == pytest.approx(0.4)
        sim.close()
        assert server.broker.get_obj("ExternalControl_Maruz", ControlLease).level == 0


# --- Example scripts ---

@pytest.mark.parametrize("script", sorted(p.name for p in SCRIPTS.glob("0*.py")))
def test_example_scripts_run_offline(script):
    result = subprocess.run([sys.executable, str(SCRIPTS / script), "--offline"],
                            capture_output=True, text=True, timeout=300)
    if script.startswith("07_"):  # no camera in the offline scene
        assert "Нет кадров" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


def test_console_starts_offline():
    result = subprocess.run([sys.executable, "-m", "scene", "--offline"], input="print(drone.position)\n",
                            capture_output=True, text=True, timeout=60,
                            cwd=Path(__file__).resolve().parent.parent / "Source")
    assert result.returncode == 0, result.stderr
    assert "Vector3(x=0.0, y=0.1, z=3.0)" in result.stdout
