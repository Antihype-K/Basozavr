import socket
import time

import pytest

from RSMA.Broker import InMemoryBroker, LocalClient
from RSMA.Client import RSMAClient
from RSMA.MockServer import MockServer
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import Float32, Pose, RobotVelocity


@pytest.fixture
def server():
    with MockServer(port=0, host="127.0.0.1") as srv:
        yield srv


@pytest.fixture
def client(server):
    with RSMAClient(host="127.0.0.1", port=server.port, timeout=2000) as c:
        yield c


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_text_commands(client, server):
    assert client.ping()
    assert client.print_message("hello") == "OK: Message printed"
    assert server.messages == ["hello"]
    assert client.restart_level().startswith("OK")
    assert client.send_command("Nope").startswith("Error: Unknown command")


def test_publish_and_get(client):
    pose = Pose(position=Vector3(1, 2, 3), timestamp=123)
    assert client.publish("DroneTargetPose_1", pose) == {"status": "ok"}
    got = client.get_state("DroneTargetPose_1", Pose)
    assert got == pose


def test_topics_are_keyed_by_type_and_name(client):
    client.publish("X", Float32(value=1.5, timestamp=1))
    assert client.get_state("X", Float32).value == 1.5
    # Same name, other type -> nothing published, default struct
    assert not is_published(client.get_state("X", RobotVelocity))


def test_unpublished_topic_returns_default(client):
    pose = client.get_state("PayloadPose", Pose)
    assert pose is not None and not is_published(pose)


def test_unknown_type_is_an_error(client):
    class NotATopic:
        pass

    assert client.get_state("x", NotATopic) is None
    assert "not found" in client.last_error
    assert client.publish("x", Float32(), topic_type="Nope")["status"] == "error"


def test_client_recovers_after_timeout():
    """REQ socket must not get stuck after an unanswered request (Lazy Pirate)."""
    port = free_port()
    with RSMAClient(host="127.0.0.1", port=port, timeout=200, retries=0) as c:
        start = time.monotonic()
        assert c.get_state("PayloadPose", Pose) is None
        assert "Timeout" in c.last_error
        assert time.monotonic() - start < 2.0

        with MockServer(port=port, host="127.0.0.1"):
            c.timeout = 2000
            assert c.ping()
            assert c.publish("T", Float32(value=2.0, timestamp=1))["status"] == "ok"


def test_local_client_matches_server_semantics():
    c = LocalClient(InMemoryBroker())
    assert not is_published(c.get_state("PayloadPose", Pose))
    c.publish("PayloadPose", Pose(timestamp=5))
    assert is_published(c.get_state("PayloadPose", Pose))
    assert c.publish("x", Float32(), topic_type="Nope")["status"] == "error"
