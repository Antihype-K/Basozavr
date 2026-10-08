from dataclasses import dataclass, field


@dataclass
class LaserScan128:
    """Mirror of RSMA.uDTP.Topics.LaserScan128."""

    ranges: list[float] = field(default_factory=list)  # Sizeof = 128
    angleMin: float = 0.0
    angleMax: float = 0.0
    angleIncrement: float = 0.0
    rangeMin: float = 0.0
    rangeMax: float = 0.0
    timestamp: int = 0
