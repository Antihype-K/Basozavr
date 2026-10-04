# utils.py
import math
from breezyslam.sensors import Laser

from RSMA.SLAM.Config import Config
from RSMA.Types.Vector3 import Vector3

class RSMALidar(Laser):
    """Adapter class for RSMA lidar to BreezySLAM"""
    def __init__(self, config: Config):
        Laser.__init__(
            self,
            config.lidar_scan_size, 
            config.lidar_scan_rate_hz, 
            config.lidar_detection_angle,
            config.lidar_max_distance_mm
        )


def rsma_to_slam_coords(rsma_x, rsma_z, rsma_rot_y_deg):
    """Transforms coordinates from RSMA to SLAM space."""
    slam_x = rsma_z    # Z in RSMA (X in SLAM)
    slam_y = -rsma_x   # -X in RSMA, (Y in SLAM)
    
    # Translate from CW (RSMA) to CCW
    slam_theta_deg = -rsma_rot_y_deg
    slam_theta_deg = (slam_theta_deg + 180) % 360 - 180
    
    return slam_x, slam_y, slam_theta_deg

def slam_to_rsma_coords(slam_x_m, slam_y_m, current_rsma_y, start_x, start_z, map_meters):
    """
    Transforms coordinates from SLAM to RSMA space.
    """
    map_center_m = map_meters / 2.0
    
    # 1. Избавляемся от смещения центра карты SLAM
    relative_slam_x = slam_x_m - map_center_m
    relative_slam_y = slam_y_m - map_center_m
    
    # 2. Обратное зеркалирование осей (из вашей к_to_slam_coords)
    # slam_x = rsma_z  =>  relative_rsma_z = slam_x
    # slam_y = -rsma_x =>  relative_rsma_x = -slam_y
    relative_rsma_x = -relative_slam_y
    relative_rsma_z = relative_slam_x
    
    # 3. Добавляем абсолютные координаты старта на сцене rsma
    absolute_rsma_x = relative_rsma_x + start_x
    absolute_rsma_z = relative_rsma_z + start_z
    
    return Vector3(x=absolute_rsma_x, y=current_rsma_y, z=absolute_rsma_z)


def calculate_local_displacement(current_pose, last_pose):
    """Calculate local displacment and rotation"""
    sync_slam_x_mm, sync_slam_y_mm, sync_slam_theta_deg = current_pose
    last_slam_x_mm, last_slam_y_mm, last_slam_theta_deg = last_pose

    d_x_global = sync_slam_x_mm - last_slam_x_mm
    d_y_global = sync_slam_y_mm - last_slam_y_mm
    
    d_theta = sync_slam_theta_deg - last_slam_theta_deg
    d_theta = (d_theta + 180) % 360 - 180
    
    # Фильтрация микрошумов
    # if abs(d_x_global) < 0.1: d_x_global = 0.0
    # if abs(d_y_global) < 0.1: d_y_global = 0.0
    # if abs(d_theta) < 0.01: d_theta = 0.0
    
    distance = math.hypot(d_x_global, d_y_global)
    
    if distance > 0:
        global_move_angle = math.atan2(d_y_global, d_x_global)
        heading_rad = math.radians(last_slam_theta_deg)
        local_move_angle = global_move_angle - heading_rad
        
        d_x_local = distance * math.cos(local_move_angle)
        d_y_local = distance * math.sin(local_move_angle)
    else:
        d_x_local = 0.0
        d_y_local = 0.0
        
    return d_x_local, d_y_local, d_theta