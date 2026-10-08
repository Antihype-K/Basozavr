from dataclasses import dataclass


@dataclass
class ControlLease:
    """Mirror of RSMA.uDTP.Topics.ControlLease (see Assets/Scripts/uDTP/ExternalControl.cs)."""

    timestamp: int = 0  # changes on every renewal
    level: int = 0  # 0 — released, 1 — velocity/target commands, 2 — direct actuator control
    duration: float = 0.5  # lease expires after this many seconds without renewal
