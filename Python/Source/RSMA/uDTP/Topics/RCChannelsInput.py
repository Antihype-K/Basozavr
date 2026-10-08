from dataclasses import dataclass, field


@dataclass
class RCChannelsInput:
    """Mirror of RSMA.uDTP.Topics.RCChannelsInput."""

    timestamp: int = 0
    channels: list[int] = field(default_factory=list)  # PWM 1000..2000
    chancount: int = 0
