from dataclasses import dataclass


@dataclass
class FlightModeCommand:
    """Mirror of RSMA.uDTP.Topics.FlightModeCommand."""

    timestamp: int = 0
    mode: int = 0
    sub_mode: int = 0
