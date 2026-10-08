"""
Дрон взлетает, облетает квадрат и садится.

    python 02_drone_square.py [--offline]
"""

import _rsma_path  # noqa: F401

from scene import connect

DRONE_ID = 1
ALTITUDE = 5.0  # высота полета, м (ось Y Unity)
SIDE = 4.0  # сторона квадрата, м

with connect(description=__doc__) as sim:
    drone = sim.drone(DRONE_ID)
    start = drone.position
    if start is None:
        raise SystemExit(f"Дрон {DRONE_ID} не найден в сцене (нет топика DronePose_{DRONE_ID})")
    print(f"Старт: {start}")

    drone.fly_to(start.x, start.y + ALTITUDE, start.z)
    print("Взлетел")

    corners = [(SIDE, 0), (SIDE, SIDE), (0, SIDE), (0, 0)]
    for dx, dz in corners:
        drone.fly_to(start.x + dx, start.y + ALTITUDE, start.z + dz)
        print(f"Точка ({dx}, {dz}) пройдена, позиция {drone.position}")

    drone.land(ground_y=start.y)
    print(f"Посадка: {drone.position}, время {sim.time:.1f} с")
