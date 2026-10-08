from dataclasses import dataclass


@dataclass
class HILGPS:
    """Mirror of RSMA.uDTP.Topics.HILGPS."""

    timestamp: int = 0
    fix_type: int = 0
    lat: int = 0  # deg * 1e7
    lon: int = 0  # deg * 1e7
    alt: int = 0  # mm MSL
    eph: int = 0
    epv: int = 0
    vel: int = 0  # cm/s
    vn: int = 0  # cm/s
    ve: int = 0  # cm/s
    vd: int = 0  # cm/s
    cog: int = 0  # cdeg
    satellites_visible: int = 0
