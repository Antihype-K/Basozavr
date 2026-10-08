from dataclasses import dataclass


@dataclass
class ArmCommand:
    """Mirror of RSMA.uDTP.Topics.ArmCommand."""

    timestamp: int = 0
    arm: int = 0  # 1 = arm, 0 = disarm
