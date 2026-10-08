from dataclasses import dataclass


@dataclass
class MotorInput:
    """Mirror of RSMA.uDTP.Topics.MotorInput."""

    timestamp: int = 0
    input: float = 0.0
