"""
Доставка груза: подъем, перелет на (dx, dz) метров, посадка груза и дронов.

    python 03_deliver.py [--dx 10] [--dz 5] [--height 3] [--speed 0.6] [--offline]

Это короткая версия миссии; полный контур управления (S-образная траектория,
гашение раскачки, CSV-лог) — python ../Source/main.py.
"""

import argparse

import _rsma_path  # noqa: F401

from scene import connect

parser = argparse.ArgumentParser()
parser.add_argument("--dx", type=float, default=10.0, help="смещение по X, м")
parser.add_argument("--dz", type=float, default=5.0, help="смещение по Z, м")
parser.add_argument("--height", type=float, default=3.0, help="высота перелета груза, м")
parser.add_argument("--speed", type=float, default=0.6, help="скорость перелета, м/с")
args, _ = parser.parse_known_args()

with connect(description=__doc__) as sim:
    swarm = sim.swarm()
    start = swarm.payload_position
    print(f"Старт: {start}")

    steps = [
        ("Подъем", lambda: swarm.lift(args.height)),
        ("Перелет", lambda: swarm.move_payload_by(args.dx, 0, args.dz, speed=args.speed)),
        ("Посадка груза", swarm.lower),
        ("Посадка дронов", swarm.land),
    ]
    for name, action in steps:
        ok = action()
        print(f"{'OK  ' if ok else 'FAIL'} {name}: груз {swarm.payload_position}")
        if not ok:
            break

    end = swarm.payload_position
    print(f"Груз перемещен на ({end.x - start.x:.2f}, {end.z - start.z:.2f}) м за {sim.time:.1f} с")
