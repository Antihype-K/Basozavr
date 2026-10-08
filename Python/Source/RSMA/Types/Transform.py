from __future__ import annotations

import math
from dataclasses import dataclass, field

from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3


@dataclass
class Transform:
    position: Vector3 = field(default_factory=Vector3)
    rotation: Quaternion = field(default_factory=Quaternion)

    def inverse_transform_point(self, target_pos: Vector3) -> Vector3:
        """
        Converts world point to local coordinates in the horizontal plane
        (only yaw is taken into account, local y is always 0).
        """
        yaw_rad = math.radians(self.rotation.to_yaw())

        diff = target_pos - self.position

        local_x = diff.x * math.cos(yaw_rad) - diff.z * math.sin(yaw_rad)
        local_z = diff.x * math.sin(yaw_rad) + diff.z * math.cos(yaw_rad)

        return Vector3(x=local_x, y=0.0, z=local_z)

    def transform_point(self, local_pos: Vector3) -> Vector3:
        """Converts local point to world coordinates (full 3D rotation)."""
        return self.position + self.rotation.rotate(local_pos)
