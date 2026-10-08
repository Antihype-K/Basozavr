from dataclasses import dataclass


@dataclass
class HILSensor:
    """Mirror of RSMA.uDTP.Topics.HILSensor."""

    timestamp: int = 0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    mag_x: float = 0.0
    mag_y: float = 0.0
    mag_z: float = 0.0
    abs_pressure: float = 0.0
    pressure_alt: float = 0.0
    temperature: float = 0.0
