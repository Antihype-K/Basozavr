from dataclasses import dataclass


@dataclass
class Float32:
    """Mirror of RSMA.uDTP.Topics.Float32."""

    value: float = 0.0
    timestamp: int = 0
