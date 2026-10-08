from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class Vector3:
    """Mirror of UnityEngine.Vector3 (left-handed, Y-up)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # --- Математические операции ---

    def magnitude(self) -> float:
        """Returns vector length."""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def sqr_magnitude(self) -> float:
        """Returns squared vector length (cheaper than magnitude())."""
        return self.x * self.x + self.y * self.y + self.z * self.z

    def distance_to(self, other: Vector3) -> float:
        """Distance from this vector to other."""
        return (self - other).magnitude()

    def normalized(self) -> Vector3:
        """Returns unit vector with the same direction (zero vector stays zero)."""
        mag = self.magnitude()
        if mag == 0:
            return Vector3(0.0, 0.0, 0.0)
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def dot(self, other: Vector3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def lerp(self, other: Vector3, t: float) -> Vector3:
        """Linear interpolation, t is clamped to [0, 1] like Vector3.Lerp."""
        t = min(1.0, max(0.0, t))
        return self + (other - self) * t

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> Vector3:
        return Vector3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar: float) -> Vector3:
        """Multiplies vector by scalar."""
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> Vector3:
        return Vector3(self.x / scalar, self.y / scalar, self.z / scalar)

    # --- Сериализация ---

    @classmethod
    def from_dict(cls, data: dict | None) -> Vector3:
        data = data or {}
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            z=float(data.get("z", 0.0)),
        )
