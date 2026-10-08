from dataclasses import dataclass, field


@dataclass
class ActuatorInputs:
    """Mirror of RSMA.uDTP.Topics.ActuatorInputs."""

    timestamp: int = 0
    size: int = 0
    inputs: list[float] = field(default_factory=list)  # Normalized motor commands 0..1
