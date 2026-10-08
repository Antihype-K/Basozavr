from dataclasses import dataclass, field

from RSMA.Types.Vector3 import Vector3


@dataclass
class TrajectoryPoint:
    """Mirror of RSMA.uDTP.Topics.TrajectoryPoint."""

    timestamp: int = 0
    position: Vector3 = field(default_factory=Vector3)
    targetVelocity: float = 0.0
