from dataclasses import dataclass

from RSMA.Types.Vector3 import Vector3


@dataclass
class MissionStatus:
    """Статус миссии для отображения в RSMA (топик MissionStatus, координаты Unity)."""
    phase: str
    progress: float
    distanceToFinish: float
    setpoint: Vector3
    finish: Vector3
    timestamp: int
