import argparse
import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from RSMA.Broker import InMemoryBroker, LocalClient
from RSMA.Client import RSMAClient
from RSMA.Time import get_unix_time_milliseconds
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import ControlLease, Float32, Pose

T = TypeVar("T")
log = logging.getLogger("scene")


class Simulation:
    """
    Подключение к сцене RSMA для скриптов управления.

        from scene import Simulation

        with Simulation() as sim:                 # Unity на localhost:5555
            drone = sim.drone(1)
            drone.fly_to(0, 5, 0)

        with Simulation.offline() as sim:         # без Unity, встроенная модель
            ...

    Все координаты — как в Unity: X — вправо, Y — вверх, Z — вперед.

    Пока скрипт управляет роботом (например, Maruz), Simulation в фоне продлевает
    «аренду» управления (топик ExternalControl_<робот>) и повторяет последнюю команду,
    поэтому встроенные Unity-контроллеры робота не перетирают команды скрипта.
    При выходе из `with` (или close()) управление возвращается Unity.
    """

    def __init__(self, host: str = "localhost", port: int = 5555, timeout: int = 1000,
                 client=None, offline_scene=None, keepalive_period: float = 0.1, lease_duration: float = 0.5):
        self.client = client if client is not None else RSMAClient(host=host, port=port, timeout=timeout)
        self.scene = offline_scene
        self.keepalive_period = keepalive_period
        self.lease_duration = lease_duration

        self._leases: dict[str, tuple[int, list[tuple[str, Any]]]] = {}
        self._last_lease_ts = 0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._t0 = time.monotonic()

        if self.scene is None:
            self._thread = threading.Thread(target=self._keepalive_loop, name="scene-keepalive", daemon=True)
            self._thread.start()

    @classmethod
    def offline(cls, **scene_kwargs) -> "Simulation":
        """Simulation на встроенной модели сцены (sim.scene_sim.OfflineScene), время виртуальное."""
        from sim.scene_sim import OfflineScene

        broker = InMemoryBroker()
        return cls(client=LocalClient(broker), offline_scene=OfflineScene(broker, **scene_kwargs))

    # --- Время ---

    @property
    def is_offline(self) -> bool:
        return self.scene is not None

    @property
    def time(self) -> float:
        """Секунды с начала работы скрипта (в офлайн-режиме — модельное время)."""
        return self.scene.time if self.scene is not None else time.monotonic() - self._t0

    def sleep(self, seconds: float) -> None:
        """Пауза. В офлайн-режиме продвигает модель сцены на это время."""
        if seconds <= 0:
            return
        if self.scene is not None:
            with self._lock:
                self.scene.advance(seconds)
        else:
            time.sleep(seconds)

    def wait_until(self, condition: Callable[[], bool], timeout: float | None = None, poll: float = 0.05) -> bool:
        """Ждет, пока condition() станет True. Возвращает False по таймауту."""
        start = self.time
        while not condition():
            if timeout is not None and self.time - start >= timeout:
                return False
            self.sleep(poll)
        return True

    # --- Топики ---

    def is_connected(self) -> bool:
        return self.client.ping()

    def get(self, topic: str, cls: type[T]) -> T | None:
        """Последнее состояние топика или None, если его еще никто не публиковал."""
        msg = self.client.get_state(topic, cls)
        if msg is not None and hasattr(msg, "timestamp") and not is_published(msg):
            return None
        return msg

    def publish(self, topic: str, message: Any) -> bool:
        return self.client.publish(topic, message).get("status") == "ok"

    def print(self, message: str) -> None:
        """Выводит сообщение в консоль Unity."""
        self.client.send_command(f"PrintMessage:{message}")

    def restart_level(self) -> None:
        self.client.send_command("RestartLevel")

    # --- Объекты сцены ---

    def drone(self, drone_id: int = 1):
        from scene.robots import Drone
        return Drone(self, drone_id)

    def maruz(self, name: str = "Maruz"):
        from scene.robots import Maruz
        return Maruz(self, name)

    def lidar(self, topic: str = "Lidar", size: int = 128):
        from scene.sensors import Lidar
        return Lidar(self, topic, size)

    def rangefinder(self, topic: str = "RangeFinder"):
        from scene.sensors import RangeFinder
        return RangeFinder(self, topic)

    def camera(self, camera_id: int = 0):
        from scene.sensors import Camera
        return Camera(self, camera_id)

    def cable_force(self, cable_id: int) -> float | None:
        msg = self.get(f"CableForce_{cable_id}", Float32)
        return None if msg is None else msg.value

    def payload_pose(self) -> Pose | None:
        return self.get("PayloadPose", Pose)

    # --- Внешнее управление (ExternalControl) ---

    def _lease_timestamp(self) -> int:
        ts = max(get_unix_time_milliseconds(), self._last_lease_ts + 1)
        self._last_lease_ts = ts
        return ts

    def _lease_messages(self, robot: str, level: int, commands: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
        lease = ControlLease(timestamp=self._lease_timestamp(), level=level, duration=self.lease_duration)
        return [(f"ExternalControl_{robot}", lease), *commands]

    def take_control(self, robot: str, level: int, commands: list[tuple[str, Any]]) -> None:
        """Берет управление роботом и публикует команды; они будут повторяться в фоне."""
        with self._lock:
            self._leases[robot] = (level, list(commands))
            self.client.publish_many(self._lease_messages(robot, level, commands))

    def release_control(self, robot: str) -> None:
        """Возвращает управление роботом Unity-контроллерам."""
        with self._lock:
            if self._leases.pop(robot, None) is not None:
                self.client.publish(f"ExternalControl_{robot}",
                                    ControlLease(timestamp=self._lease_timestamp(), level=0, duration=0.0))

    def _keepalive_loop(self) -> None:
        while not self._stop.wait(self.keepalive_period):
            with self._lock:
                messages = []
                for robot, (level, commands) in self._leases.items():
                    messages += self._lease_messages(robot, level, commands)
                if messages:
                    try:
                        self.client.publish_many(messages)
                    except Exception as e:  # клиент закрыт или потерял связь
                        log.debug("keepalive failed: %s", e)

    # --- Жизненный цикл ---

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        for robot in list(self._leases):
            try:
                self.release_control(robot)
            except Exception as e:
                log.debug("release failed: %s", e)
        self.client.close()

    def __enter__(self) -> "Simulation":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def connect(argv: list[str] | None = None, description: str | None = None) -> Simulation:
    """
    Simulation по аргументам командной строки скрипта:
    --host, --port (Unity) или --offline (встроенная модель).
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--host", default="localhost", help="адрес Unity (RSMA NetMQ сервер)")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--offline", action="store_true", help="без Unity, на встроенной модели сцены")
    parser.add_argument("-v", "--verbose", action="store_true")
    args, _ = parser.parse_known_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    if args.offline:
        log.info("Офлайн-режим: встроенная модель сцены")
        return Simulation.offline()

    sim = Simulation(host=args.host, port=args.port)
    if not sim.is_connected():
        log.warning("RSMA не отвечает на %s:%d — запущена ли сцена в Unity?", args.host, args.port)
    return sim
