"""
Робот Maruz объезжает квадрат по точкам и возвращается.

    python 05_maruz_waypoints.py [--offline]
"""

import _rsma_path  # noqa: F401

from scene import connect

SIDE = 3.0  # м
SPEED = 0.6  # м/с

with connect(description=__doc__) as sim:
    maruz = sim.maruz()
    start = maruz.position
    if start is None:
        raise SystemExit("Maruz не найден (нет топика MaruzPose): откройте сцену SupremeFlat")

    route = [(start.x + dx, start.z + dz) for dx, dz in [(0, SIDE), (SIDE, SIDE), (SIDE, 0), (0, 0)]]
    for x, z in route:
        ok = maruz.go_to(x, z, speed=SPEED)
        print(f"{'OK  ' if ok else 'FAIL'} ({x:.1f}, {z:.1f}) -> {maruz.position}")
        if not ok:
            break

    maruz.rotate_to(0.0)
    maruz.release()
    print(f"Маршрут пройден за {sim.time:.1f} с")
