"""
Интерактивная консоль управления сценой:

    python -m scene              # запустит Unity со сценой, если она еще не запущена
    python -m scene --offline    # встроенная модель сцены
"""

import code
import sys

from scene import Camera, Drone, Quaternion, Simulation, Swarm, Vector3, connect

BANNER = """RSMA: рой дронов с грузом. Координаты Unity: X — вправо, Y — вверх, Z — вперед.
  swarm                       — рой: swarm.lift(3), swarm.move_payload_by(10, 0, 0), swarm.lower(), swarm.land()
  swarm.payload_position      — где груз;  swarm.cable_forces() — натяжение тросов, Н
  d = sim.drone(1)            — d.position, d.fly_to(0, 5, 0), d.move_by(1, 0, 0), d.hover(), d.land()
  sim.find_drones()           — номера дронов в сцене;  sim.sleep(1);  sim.print("text") — в консоль Unity
Выход: Ctrl+D (Ctrl+Z, Enter в Windows)."""


def main(argv=None) -> None:
    sim = connect(argv, description="Interactive RSMA scene console")
    namespace = {"sim": sim, "Vector3": Vector3, "Quaternion": Quaternion, "Simulation": Simulation,
                 "Drone": Drone, "Swarm": Swarm, "Camera": Camera}
    try:
        namespace["swarm"] = sim.swarm()
    except RuntimeError as e:
        print(f"swarm недоступен: {e}")
    try:
        code.interact(banner=BANNER, local=namespace, exitmsg="")
    finally:
        sim.close()


if __name__ == "__main__":
    main(sys.argv[1:])
