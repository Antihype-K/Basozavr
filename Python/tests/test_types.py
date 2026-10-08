import math

import pytest

from RSMA.Mathf import clamp, delta_angle, lerp, move_towards
from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Transform import Transform
from RSMA.Types.Vector3 import Vector3


def approx_v(a: Vector3, b: Vector3, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b, strict=True))


def test_vector_ops():
    a, b = Vector3(1, 2, 3), Vector3(4, 5, 6)
    assert a + b == Vector3(5, 7, 9)
    assert b - a == Vector3(3, 3, 3)
    assert 2 * a == a * 2 == Vector3(2, 4, 6)
    assert -a == Vector3(-1, -2, -3)
    assert a / 2 == Vector3(0.5, 1, 1.5)
    assert a.dot(b) == 32
    assert Vector3(1, 0, 0).cross(Vector3(0, 1, 0)) == Vector3(0, 0, 1)
    assert Vector3(3, 4, 0).magnitude() == 5
    assert Vector3().normalized() == Vector3()
    assert list(a) == [1, 2, 3]
    assert a.lerp(b, 2.0) == b


@pytest.mark.parametrize("euler", [(0, 35, 0), (20, 35, 10), (-30, -120, 45), (10, 170, -5)])
def test_to_yaw_matches_unity_euler_y(euler):
    q = Quaternion.euler(*euler)
    assert q.to_yaw() == pytest.approx(euler[1], abs=1e-6)


def test_rotate_matches_unity_convention():
    # Unity: Quaternion.Euler(0, 90, 0) * Vector3.forward == Vector3.right
    q = Quaternion.euler(0, 90, 0)
    assert approx_v(q.rotate(Vector3(0, 0, 1)), Vector3(1, 0, 0))
    assert approx_v(q.inverse().rotate(q.rotate(Vector3(1, 2, 3))), Vector3(1, 2, 3))


def test_quaternion_from_dict_ignores_unity_extras():
    data = {"x": 0.0, "y": 0.7071, "z": 0.0, "w": 0.7071, "eulerAngles": {"x": 0, "y": 90, "z": 0}, "normalized": {}}
    q = Quaternion.from_dict(data)
    assert q.to_yaw() == pytest.approx(90, abs=0.01)


def test_transform_round_trip():
    t = Transform(Vector3(1, 0, 2), Quaternion.euler(0, 30, 0))
    local = Vector3(0.5, 0.0, -1.5)
    assert approx_v(t.inverse_transform_point(t.transform_point(local)), local)


def test_mathf():
    assert delta_angle(350, 10) == 20
    assert delta_angle(10, 350) == -20
    assert clamp(5, 0, 1) == 1
    assert lerp(0, 10, 0.25) == 2.5
    assert move_towards(0, 10, 3) == 3
    assert move_towards(9, 10, 3) == 10
    assert math.isclose(delta_angle(0, 180), -180)
