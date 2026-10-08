from __future__ import annotations

import math
from dataclasses import dataclass

from RSMA.Types.Vector3 import Vector3


@dataclass
class Quaternion:
    """Mirror of UnityEngine.Quaternion (x, y, z, w)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    @classmethod
    def identity(cls) -> Quaternion:
        return cls(0.0, 0.0, 0.0, 1.0)

    @classmethod
    def angle_axis(cls, angle_deg: float, axis: Vector3) -> Quaternion:
        """Rotation by angle_deg around axis (same as Quaternion.AngleAxis)."""
        axis = axis.normalized()
        half = math.radians(angle_deg) / 2.0
        s = math.sin(half)
        return cls(axis.x * s, axis.y * s, axis.z * s, math.cos(half))

    @classmethod
    def euler(cls, x_deg: float, y_deg: float, z_deg: float) -> Quaternion:
        """
        Same as Unity Quaternion.Euler: rotates around Z, then X, then Y
        (world axes), i.e. q = qY * qX * qZ.
        """
        qx = cls.angle_axis(x_deg, Vector3(1, 0, 0))
        qy = cls.angle_axis(y_deg, Vector3(0, 1, 0))
        qz = cls.angle_axis(z_deg, Vector3(0, 0, 1))
        return qy * qx * qz

    def to_yaw(self) -> float:
        """
        Returns rotation around the vertical Y axis in degrees, in (-180, 180].
        Equals Unity's transform.eulerAngles.y (wrapped), also for tilted bodies.
        """
        # Unity uses YXZ order: yaw = atan2(R[0][2], R[2][2])
        siny = 2.0 * (self.w * self.y + self.x * self.z)
        cosy = 1.0 - 2.0 * (self.x * self.x + self.y * self.y)
        return math.degrees(math.atan2(siny, cosy))

    def normalize(self) -> Quaternion:
        """Returns normalized quaternion (identity for zero quaternion)."""
        mag = math.sqrt(self.x**2 + self.y**2 + self.z**2 + self.w**2)
        if mag == 0:
            return Quaternion(0, 0, 0, 1)
        return Quaternion(self.x / mag, self.y / mag, self.z / mag, self.w / mag)

    def inverse(self) -> Quaternion:
        """Inverse rotation (conjugate of the normalized quaternion)."""
        q = self.normalize()
        return Quaternion(-q.x, -q.y, -q.z, q.w)

    def rotate(self, v: Vector3) -> Vector3:
        """Rotates vector v (same as Unity `q * v`)."""
        qv = Quaternion(v.x, v.y, v.z, 0.0)
        r = self * qv * Quaternion(-self.x, -self.y, -self.z, self.w)
        return Vector3(r.x, r.y, r.z)

    def __mul__(self, other: Quaternion) -> Quaternion:
        """
        Composition of two rotations (Q1 * Q2 applies Q2 first, then Q1).
        Note: Q1 * Q2 != Q2 * Q1.
        """
        return Quaternion(
            w=self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
            x=self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            y=self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            z=self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
        )

    @classmethod
    def from_dict(cls, data: dict | None) -> Quaternion:
        """Builds Quaternion from JSON; extra keys (eulerAngles, normalized) are ignored."""
        data = data or {}
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            z=float(data.get("z", 0.0)),
            w=float(data.get("w", 1.0)),
        )
