from dataclasses import dataclass


@dataclass
class RobotVelocity:
    """Mirror of RSMA.uDTP.Topics.RobotVelocity."""

    timestamp: int = 0
    linearVelocity: float = 0.0
    angularVelocity: float = 0.0
