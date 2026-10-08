"""
Робот Maruz: езда по командам скорости.

    python 04_maruz_drive.py [--offline]

Скорость: linear — м/с (вперед > 0), angular — рад/с (влево > 0).
"""

import math

import _rsma_path  # noqa: F401

from scene import connect

with connect(description=__doc__) as sim:
    maruz = sim.maruz()
    if maruz.position is None:
        raise SystemExit("Maruz не найден (нет топика MaruzPose): откройте сцену SupremeFlat")
    print(f"Старт: {maruz.position}, курс {maruz.heading:.1f}°")

    maruz.drive(0.5, duration=2.0)  # 1 м вперед
    print(f"Проехал вперед: {maruz.position}")

    maruz.turn(math.pi / 4, duration=2.0)  # 90° влево
    print(f"Повернул: курс {maruz.heading:.1f}°")

    maruz.drive(0.4, angular=0.4, duration=3.0)  # дуга
    print(f"Дуга: {maruz.position}, курс {maruz.heading:.1f}°")

    maruz.set_wheels(0.05, -0.05, duration=1.0)  # прямое управление колесами
    maruz.release()  # вернуть управление Unity
    print("Готово")
