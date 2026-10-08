from dataclasses import dataclass, field

from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3


@dataclass
class Pose:
    """Mirror of RSMA.uDTP.Topics.Pose."""

    position: Vector3 = field(default_factory=Vector3)
    rotation: Quaternion = field(default_factory=Quaternion)
    timestamp: int = 0
