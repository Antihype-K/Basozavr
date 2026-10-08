"""
Проверка связи со сценой: дроны, груз, тросы.

    python 01_hello.py            # запустит Unity со сценой, если она еще не запущена
    python 01_hello.py --offline  # без Unity
"""

import _rsma_path  # noqa: F401

from scene import connect

with connect(description=__doc__) as sim:
    sim.print("Привет из Python!")

    payload = sim.payload_pose()
    print(f"Груз: {payload.position if payload else 'не найден (нет PayloadPose)'}")

    for drone in sim.drones():
        force = drone.cable_force
        cable = f", трос {force:.1f} Н" if force is not None else ""
        print(f"Дрон {drone.id}: {drone.position}{cable}")
