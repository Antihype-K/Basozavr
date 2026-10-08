from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from dataclasses import dataclass

import math

@dataclass
class Pose:
    position: Vector3
    rotation: Quaternion
    timestamp: int