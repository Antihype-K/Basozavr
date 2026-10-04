from dataclasses import dataclass

@dataclass
class LaserScan256:
    ranges: list[float] # Sizeof = 256
    angleMin: float
    angleMax: float
    angleIncrement: float
    rangeMin: float
    rangeMax: float
    timestamp: int 