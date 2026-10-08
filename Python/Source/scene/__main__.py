"""
Интерактивная консоль управления сценой:

    python -m scene              # Unity на localhost:5555
    python -m scene --offline    # встроенная модель сцены
"""

import code
import sys

from scene import Camera, Drone, Lidar, Maruz, Quaternion, RangeFinder, Simulation, Vector3, connect

BANNER = """RSMA scene console. Координаты Unity: X — вправо, Y — вверх, Z — вперед.
  sim                      — подключение (sim.sleep(1), sim.print("text"), sim.get(topic, Type))
  drone = sim.drone(1)     — drone.fly_to(0, 5, 0), drone.position, drone.land()
  maruz = sim.maruz()      — maruz.drive(0.5, duration=2), maruz.turn(1.0, 1), maruz.go_to(3, 4), maruz.release()
  sim.lidar().min_distance(), sim.rangefinder().distance(), sim.camera(0).save("frame.png")
Выход: Ctrl+D (Ctrl+Z, Enter в Windows)."""


def main(argv=None) -> None:
    sim = connect(argv, description="Interactive RSMA scene console")
    namespace = {
        "sim": sim, "drone": sim.drone(1), "maruz": sim.maruz(),
        "Vector3": Vector3, "Quaternion": Quaternion, "Simulation": Simulation,
        "Drone": Drone, "Maruz": Maruz, "Lidar": Lidar, "RangeFinder": RangeFinder, "Camera": Camera,
    }
    try:
        code.interact(banner=BANNER, local=namespace, exitmsg="")
    finally:
        sim.close()


if __name__ == "__main__":
    main(sys.argv[1:])
