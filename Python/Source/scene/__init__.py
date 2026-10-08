"""
Управление сценой доставки груза роем (RSMA, Unity) из Python-скриптов.

    from scene import connect

    with connect() as sim:            # запустит Unity со сценой, если она еще не запущена
        swarm = sim.swarm()           # все дроны и груз
        swarm.lift(3.0)
        swarm.move_payload_by(10, 0, 0)
        swarm.lower()
        swarm.land()

Координаты — как в Unity: X — вправо, Y — вверх, Z — вперед.
Интерактивная консоль: python -m scene [--offline]
"""

from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from scene.launcher import UnityLaunchError, launch_unity
from scene.robots import Drone, Swarm
from scene.sensors import Camera
from scene.simulation import Simulation, connect

__all__ = ["Camera", "Drone", "Quaternion", "Simulation", "Swarm", "UnityLaunchError", "Vector3", "connect",
           "launch_unity"]
