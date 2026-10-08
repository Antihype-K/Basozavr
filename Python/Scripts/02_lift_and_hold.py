"""
Рой поднимает груз, держит его в воздухе и опускает обратно.

    python 02_lift_and_hold.py [--height 3] [--hold 10] [--offline]
"""

import argparse

import _rsma_path  # noqa: F401

from scene import connect

parser = argparse.ArgumentParser()
parser.add_argument("--height", type=float, default=3.0, help="высота подъема груза, м")
parser.add_argument("--hold", type=float, default=10.0, help="сколько секунд держать, с")
args, _ = parser.parse_known_args()

with connect(description=__doc__) as sim:
    swarm = sim.swarm()
    print(f"Дронов: {len(swarm.drones)}, груз: {swarm.payload_position}")

    swarm.lift(args.height)
    print(f"Груз поднят: {swarm.payload_position}")

    start = sim.time
    while sim.time - start < args.hold:
        forces = swarm.cable_forces()
        print(f"t={sim.time - start:4.1f} с  груз y={swarm.payload_position.y:.2f} м  "
              f"тросы: {', '.join(f'{f:.0f}' for f in forces.values() if f is not None)} Н")
        sim.sleep(1.0)

    swarm.lower()
    swarm.land()
    print(f"Готово: груз {swarm.payload_position}, время {sim.time:.1f} с")
