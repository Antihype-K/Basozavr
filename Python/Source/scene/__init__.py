"""
Управление сценой RSMA (Unity) из Python-скриптов.

    from scene import connect

    with connect() as sim:            # --host/--port или --offline из командной строки
        sim.drone(1).fly_to(0, 5, 0)
        sim.maruz().go_to(3, 4)

Координаты — как в Unity: X — вправо, Y — вверх, Z — вперед.
Интерактивная консоль: python -m scene [--offline]
"""

from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from scene.robots import Drone, Maruz
from scene.sensors import Camera, Lidar, RangeFinder
from scene.simulation import Simulation, connect

__all__ = ["Camera", "Drone", "Lidar", "Maruz", "Quaternion", "RangeFinder", "Simulation", "Vector3", "connect"]
