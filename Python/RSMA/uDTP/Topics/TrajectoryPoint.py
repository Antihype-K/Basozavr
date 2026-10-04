from dataclasses import dataclass
from RSMA.Types.Vector3 import Vector3

import time

@dataclass
class TrajectoryPoint:
    timestamp: int
    position: Vector3
    targetVelocity: float = 0.0