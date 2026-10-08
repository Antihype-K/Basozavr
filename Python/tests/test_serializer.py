import dataclasses
import json

import pytest

from RSMA.Serializer import RSMASerializer
from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import TOPIC_TYPES, CameraFramePacket, LaserScan128, Pose


@pytest.mark.parametrize("name", sorted(TOPIC_TYPES))
def test_every_topic_round_trips_through_json(name):
    cls = TOPIC_TYPES[name]
    obj = cls()
    restored = RSMASerializer.from_dict(cls, json.loads(json.dumps(RSMASerializer.to_dict(obj))))
    assert restored == obj


@pytest.mark.parametrize("name", sorted(TOPIC_TYPES))
def test_unpublished_default_is_detected(name):
    cls = TOPIC_TYPES[name]
    msg = RSMASerializer.from_dict(cls, RSMASerializer.default_dict(cls))
    if "timestamp" in {f.name for f in dataclasses.fields(cls)}:
        assert not is_published(msg)
    # MISSING must never leak into objects
    for f in dataclasses.fields(cls):
        assert getattr(msg, f.name) is not dataclasses.MISSING


def test_pose_from_newtonsoft_json():
    # What Newtonsoft produces for a Unity Pose struct (extra Vector3/Quaternion properties)
    data = {
        "timestamp": 1700000000000,
        "position": {"x": 1.5, "y": 2.0, "z": -3.0, "normalized": {"x": 0.3}, "magnitude": 3.9, "sqrMagnitude": 15.25},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0, "eulerAngles": {"x": 0, "y": 0, "z": 0}},
    }
    pose = RSMASerializer.from_dict(Pose, data)
    assert pose.position == Vector3(1.5, 2.0, -3.0)
    assert pose.rotation == Quaternion(0, 0, 0, 1)
    assert is_published(pose)


def test_missing_fields_use_defaults_not_missing():
    scan = RSMASerializer.from_dict(LaserScan128, {"angleMin": -1.0, "timestamp": 5})
    assert scan.ranges == []
    assert scan.angleMin == -1.0
    assert scan.rangeMax == 0.0


def test_bytes_are_base64_like_newtonsoft():
    frame = CameraFramePacket(width=1, height=1, channels=3, timestamp=1, frameSequence=7, pixelData=b"\x01\x02\xff")
    data = RSMASerializer.to_dict(frame)
    assert data["pixelData"] == "AQL/"
    assert RSMASerializer.from_dict(CameraFramePacket, data) == frame


def test_int_and_float_coercion():
    pose = RSMASerializer.from_dict(Pose, {"position": {"x": 1, "y": 2, "z": 3}, "timestamp": 10.0})
    assert isinstance(pose.position.x, float)
    assert pose.timestamp == 10 and isinstance(pose.timestamp, int)


def test_numpy_values_serialize():
    np = pytest.importorskip("numpy")
    data = RSMASerializer.to_dict(LaserScan128(ranges=np.array([1.0, 2.0]), angleMin=np.float32(0.5)))
    assert json.loads(json.dumps(data))["ranges"] == [1.0, 2.0]
