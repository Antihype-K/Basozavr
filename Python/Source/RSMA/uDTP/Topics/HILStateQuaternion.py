from dataclasses import dataclass, field


@dataclass
class HILStateQuaternion:
    """Mirror of RSMA.uDTP.Topics.HILStateQuaternion."""

    timestamp: int = 0
    orientation: list[float] = field(default_factory=list)  # [w, x, y, z]
    rollspeed: float = 0.0
    yawspeed: float = 0.0
    pitchspeed: float = 0.0
    lat: int = 0
    lon: int = 0
    alt: int = 0
    vn: int = 0
    ve: int = 0
    vd: int = 0
