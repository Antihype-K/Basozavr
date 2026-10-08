"""
Проверка связи со сценой: что сейчас публикуется.

    python 01_hello.py            # Unity на localhost:5555
    python 01_hello.py --offline  # без Unity
"""

import _rsma_path  # noqa: F401

from scene import connect

with connect(description=__doc__) as sim:
    if not sim.is_offline and not sim.is_connected():
        raise SystemExit("Нет связи с Unity: запустите сцену (ServerApp поднимает сервер на порту 5555)")

    sim.print("Привет из Python!")

    for i in range(1, 7):
        pos = sim.drone(i).position
        if pos is not None:
            print(f"Дрон {i}: {pos}")

    maruz = sim.maruz()
    if maruz.position is not None:
        print(f"Maruz: {maruz.position}, курс {maruz.heading:.1f}°")

    payload = sim.payload_pose()
    if payload is not None:
        print(f"Груз: {payload.position}")

    lidar = sim.lidar()
    if lidar.scan() is not None:
        print(f"Лидар: ближайшее препятствие {lidar.min_distance():.2f} м")

    distance = sim.rangefinder().distance()
    if distance is not None:
        print(f"Дальномер: {distance:.2f} м")
