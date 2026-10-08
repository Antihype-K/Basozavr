"""
Несколько дронов летят по кругу в формации (без груза).

    python 03_drones_circle.py [--offline]

Внимание: в сцене с RSMASwarmEnvironment дроны привязаны тросами к грузу —
для этого примера лучше сцена без троса или контур управления роем (main.py).
"""

import math

import _rsma_path  # noqa: F401

from scene import Vector3, connect

DRONE_IDS = [1, 2, 3, 4, 5, 6]
CENTER = Vector3(0.0, 6.0, 0.0)
RADIUS = 4.0
LAPS = 1
PERIOD = 20.0  # секунд на круг

with connect(description=__doc__) as sim:
    drones = [sim.drone(i) for i in DRONE_IDS if sim.drone(i).position is not None]
    if not drones:
        raise SystemExit("В сцене нет дронов (топики DronePose_i)")
    print(f"Дронов в формации: {len(drones)}")

    def slot(k: int, phase: float) -> Vector3:
        a = phase + 2 * math.pi * k / len(drones)
        return Vector3(CENTER.x + RADIUS * math.cos(a), CENTER.y, CENTER.z + RADIUS * math.sin(a))

    # Занять места в формации
    for k, d in enumerate(drones):
        d.set_target(slot(k, 0.0))
    sim.wait_until(lambda: all((d.distance_to_target() or 1e9) < 0.5 for d in drones), timeout=60)

    # Вращение формации
    start = sim.time
    while sim.time - start < LAPS * PERIOD:
        phase = 2 * math.pi * (sim.time - start) / PERIOD
        for k, d in enumerate(drones):
            d.set_target(slot(k, phase))
        sim.sleep(0.1)

    for d in drones:
        d.hover()
    print("Готово")
