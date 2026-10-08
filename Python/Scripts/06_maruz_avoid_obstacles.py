"""
Робот едет вперед и объезжает препятствия по лидару.

    python 06_maruz_avoid_obstacles.py [--offline] [--lidar TOPIC] [--time 60]

Нужен лидар на роботе, публикующий LaserScan128 в топик (по умолчанию "Lidar").
"""

import argparse

import _rsma_path  # noqa: F401

from scene import connect

parser = argparse.ArgumentParser()
parser.add_argument("--lidar", default="Lidar")
parser.add_argument("--time", type=float, default=60.0)
args, _ = parser.parse_known_args()

SAFE_DISTANCE = 1.2  # м
SPEED = 0.5
TURN = 1.0  # рад/с

with connect(description=__doc__) as sim:
    maruz = sim.maruz()
    lidar = sim.lidar(args.lidar)
    if maruz.position is None or lidar.scan() is None:
        raise SystemExit("Нужны топики MaruzPose и лидар " + args.lidar)

    start = sim.time
    while sim.time - start < args.time:
        # Сектор ±30° вперед: углы 330..360 и 0..30
        front = [d for a in range(-30, 31, 5) if (d := lidar.distance_at(a % 360)) is not None]
        left = lidar.distance_at(270) or 0.0
        right = lidar.distance_at(90) or 0.0
        if front and min(front) < SAFE_DISTANCE:
            maruz.drive(0.0, TURN if left > right else -TURN)  # поворот в более свободную сторону
        else:
            maruz.drive(SPEED)
        sim.sleep(0.1)

    maruz.release()
    print(f"Позиция: {maruz.position}")
