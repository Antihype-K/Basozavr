from dataclasses import dataclass


@dataclass
class HILOpticalFlow:
    """Mirror of RSMA.uDTP.Topics.HILOpticalFlow."""

    timestamp: int = 0
    time_usec: int = 0
    sensor_id: int = 0
    integration_time_us: float = 0.0
    integrated_x: float = 0.0
    integrated_y: float = 0.0
    integrated_xgyro: float = 0.0
    integrated_ygyro: float = 0.0
    integrated_zgyro: float = 0.0
    temperature: int = 0
    quality: int = 0
    time_delta_distance_us: float = 0.0
    distance: float = 0.0
