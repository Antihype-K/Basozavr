from dataclasses import dataclass

@dataclass
class RobotVelocity:
    timestamp: int
    linearVelocity: float = 0.0
    angularVelocity: float = 0.0