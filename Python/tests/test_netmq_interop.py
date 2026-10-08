"""
Python RSMAClient against the real Unity NetMQ server code (C#), hosted by Tools/NetMQHost.

Skipped unless NETMQ_HOST is set to the built host, e.g.:
    dotnet build ../Tools/NetMQHost -c Release -o ../Tools/NetMQHost/out
    NETMQ_HOST=../Tools/NetMQHost/out/NetMQHost.dll pytest tests/test_netmq_interop.py
"""

import os
import socket
import subprocess
import sys

import pytest

from RSMA.Client import RSMAClient
from RSMA.MockServer import MockServer
from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import CameraFramePacket, Float32, HILSensor, LaserScan128, Pose

HOST_DLL = os.environ.get("NETMQ_HOST")
pytestmark = pytest.mark.skipif(not HOST_DLL, reason="NETMQ_HOST is not set (see module docstring)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Host:
    def __init__(self, port: int):
        cmd = ["dotnet", HOST_DLL] if HOST_DLL.endswith(".dll") else [HOST_DLL]
        self.proc = subprocess.Popen(cmd + [str(port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=sys.stderr, text=True)
        assert self.proc.stdout.readline().strip() == "READY"

    def command(self, cmd: str) -> str:
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        return self.proc.stdout.readline().strip()

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
            self.proc.wait(10)


@pytest.fixture
def host_port():
    port = free_port()
    host = Host(port)
    yield host, port
    host.close()


@pytest.fixture
def client(host_port):
    _, port = host_port
    with RSMAClient("127.0.0.1", port, timeout=2000, retries=0) as c:
        yield c


def test_text_commands(client):
    assert client.ping()
    assert client.print_message("hello from python") == "OK: Message printed"
    assert client.send_command("Bogus").startswith("Error")


def test_pose_round_trip(client):
    pose = Pose(Vector3(1.5, -2.0, 3.25), Quaternion.euler(10, 45, 0), 1234)
    assert client.publish("DroneTargetPose_1", pose) == {"status": "ok"}
    got = client.get_state("DroneTargetPose_1", Pose)
    assert got.position == pose.position and got.timestamp == 1234
    assert got.rotation.to_yaw() == pytest.approx(45, abs=1e-3)


def test_unpublished_topic(client):
    assert not is_published(client.get_state("PayloadPose", Pose))


def test_arrays_bytes_and_snake_case(client):
    scan = LaserScan128(ranges=[float(i) for i in range(128)], angleMin=0.5, angleMax=360.0, timestamp=9)
    client.publish("Lidar", scan)
    assert client.get_state("Lidar", LaserScan128).ranges == scan.ranges

    frame = CameraFramePacket(2, 1, 3, 7, 42, bytes([1, 2, 3, 250, 251, 252]))
    client.publish("Camera_0", frame)
    assert client.get_state("Camera_0", CameraFramePacket) == frame

    client.publish("HILSensor_0", HILSensor(timestamp=77, accel_z=-9.81))
    assert client.get_state("HILSensor_0", HILSensor).accel_z == pytest.approx(-9.81)


def test_errors_are_valid_json(client):
    r = client.publish("x", Float32(), topic_type='No"Such')
    assert r["status"] == "error" and "not found" in r["message"]


def test_stop_and_restart_on_same_port(host_port, client):
    host, _ = host_port
    client.publish("CableForce_1", Float32(value=12.5, timestamp=5))
    assert host.command("stop") == "running=false"
    client.timeout = 300
    assert not client.ping()
    assert host.command("run") == "running=true"
    client.timeout = 2000
    assert client.ping()
    assert client.get_state("CableForce_1", Float32).value == 12.5


def test_busy_port_is_reported():
    with MockServer(port=0, host="*") as occupied:
        host = Host(occupied.port)
        try:
            assert host.command("state") == "running=false"
        finally:
            host.close()


def test_batch(client):
    results = client.publish_many([(f"CableForce_{i}", Float32(value=float(i), timestamp=i)) for i in range(1, 7)])
    assert all(r == {"status": "ok"} for r in results)
    states = client.get_states([(f"CableForce_{i}", Float32) for i in range(1, 7)] + [("PayloadPose", Pose)])
    assert client.supports_batch is True
    assert [s.value for s in states[:6]] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert not is_published(states[6])
