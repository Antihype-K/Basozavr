from dataclasses import dataclass

@dataclass
class LaserScan128:
    ranges: list[float] # Sizeof = 128
    angleMin: float
    angleMax: float
    angleIncrement: float
    rangeMin: float
    rangeMax: float
    timestamp: int 