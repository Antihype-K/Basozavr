from RSMA.Types.Vector3 import Vector3
from RSMA.Types.Quaternion import Quaternion

from dataclasses import dataclass

import math

@dataclass
class Transform:
    position: Vector3
    rotation: Quaternion

    def inverse_transform_point(self, target_pos: Vector3) -> Vector3:
        yaw_rad = math.radians(self.rotation.to_yaw())

        diff = target_pos - self.position

        local_x = diff.x * math.cos(yaw_rad) - diff.z * math.sin(yaw_rad)
        local_z = diff.x * math.sin(yaw_rad) + diff.z * math.cos(yaw_rad)

        return Vector3(x=local_x, y=0.0, z=local_z)