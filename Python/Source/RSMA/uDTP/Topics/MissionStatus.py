from dataclasses import dataclass, field

from RSMA.Types.Vector3 import Vector3


@dataclass
class MissionStatus:
    """
    Mirror of RSMA.uDTP.Topics.MissionStatus: mission state published by the Python
    controller and shown in RSMA by SwarmLiveView (Unity coordinates).
    """

    timestamp: int = 0
    phase: str = ""  # LIFT, TRAJECTORY, HOVER, LAND, LAND_DRONES, FINISHED
    progress: float = 0.0  # share of the way to the delivery point, 0..1
    distanceToFinish: float = 0.0
    setpoint: Vector3 = field(default_factory=Vector3)  # payload set point
    finish: Vector3 = field(default_factory=Vector3)
