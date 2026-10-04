from dataclasses import dataclass

@dataclass
class Config:
    """Lidar, simulation and map settings"""
    map_size_pixels: int = 1000
    """"Map size in pixels"""
    map_size_metersP: float = 60.0
    """"Map size in pixels"""
    lidar_scan_size: int = 256
    """"Lidar ray count"""
    lidar_scan_rate_hz: float = 50
    """"Lidar distances update rate"""
    lidar_max_distance_mm: float = 20000
    """"Lidar max measure distance"""
    lidar_sigma_xy: float = 75.0
    """Max XY deviation in mm"""
    lidar_sigma_angle: float = 5
    """Max angle deviation in deg"""
    lidar_detection_angle: float = 360
    """Lidar detection angle in deg"""
    max_sync_time_diff_ms = 35
    """Max time deviation in ms"""
    loop_delay_sec = 0.01
    """Update loop delay in s"""