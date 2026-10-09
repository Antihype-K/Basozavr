import argparse
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from RSMA.Broker import InMemoryBroker, LocalClient
from RSMA.Client import RSMAClient
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import Float32, Pose

T = TypeVar("T")
log = logging.getLogger("scene")


class Simulation:
    """
    Подключение к сцене доставки груза роем для скриптов управления.

        from scene import connect

        with connect() as sim:                # запустит Unity со сценой, если она еще не запущена
            swarm = sim.swarm()
            swarm.lift(3.0)

        with Simulation.offline() as sim:     # без Unity, встроенная модель
            ...

    Все координаты — как в Unity: X — вправо, Y — вверх, Z — вперед.
    """

    def __init__(self, host: str = "localhost", port: int = 5555, timeout: int = 1000,
                 client=None, offline_scene=None, unity=None, close_unity: bool = False):
        self.client = client if client is not None else RSMAClient(host=host, port=port, timeout=timeout)
        self.scene = offline_scene
        self.unity = unity  # scene.launcher.UnityInstance, если Unity запускал скрипт
        self.close_unity = close_unity
        self._t0 = time.monotonic()

    @classmethod
    def offline(cls, **scene_kwargs) -> "Simulation":
        """Simulation на встроенной модели сцены (дроны, тросы, груз), время виртуальное."""
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

    def find_drones(self, max_id: int = 16) -> list[int]:
        """Номера дронов, которые есть в сцене (публикуют DronePose_i)."""
        poses = self.client.get_states([(f"DronePose_{i}", Pose) for i in range(1, max_id + 1)])
        return [i for i, pose in enumerate(poses, start=1) if is_published(pose)]

    def drone(self, drone_id: int = 1):
        from scene.robots import Drone
        return Drone(self, drone_id)

    def drones(self) -> list:
        return [self.drone(i) for i in self.find_drones()]

    def swarm(self, drone_ids: list[int] | None = None, **kwargs):
        from scene.robots import Swarm
        return Swarm(self, drone_ids, **kwargs)

    def payload_pose(self) -> Pose | None:
        return self.get("PayloadPose", Pose)

    def cable_force(self, cable_id: int) -> float | None:
        msg = self.get(f"CableForce_{cable_id}", Float32)
        return None if msg is None else msg.value

    def camera(self, camera_id: int = 0):
        from scene.sensors import Camera
        return Camera(self, camera_id)

    def wait_for_scene(self, timeout: float = 60.0) -> bool:
        """Ждет, пока в сцене появятся груз и дроны (после запуска Play они создаются не сразу)."""
        ok = self.wait_until(lambda: self.payload_pose() is not None and bool(self.find_drones()), timeout, poll=0.5)
        if not ok:
            log.warning("За %.0f с в сцене не появились груз и дроны (PayloadPose, DronePose_i). "
                        "Открыта сцена с RSMASwarmEnvironment?", timeout)
        return ok

    # --- Жизненный цикл ---

    def close(self) -> None:
        self.client.close()
        if self.close_unity and self.unity is not None:
            self.unity.stop()

    def __enter__(self) -> "Simulation":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def add_connection_args(parser: argparse.ArgumentParser) -> None:
    """Общие аргументы подключения к сцене (скрипты и main.py)."""
    from scene.launcher import DEFAULT_SCENE

    group = parser.add_argument_group("подключение к RSMA")
    group.add_argument("--host", default="localhost", help="адрес Unity (RSMA NetMQ сервер)")
    group.add_argument("--port", type=int, default=5555)
    group.add_argument("--no-launch", action="store_true",
                       help="не запускать Unity автоматически, если сцена не отвечает")
    group.add_argument("--scene", default=DEFAULT_SCENE, help="сцена для автозапуска")
    group.add_argument("--unity", default=None, help="путь к редактору Unity (иначе RSMA_UNITY или Unity Hub)")
    group.add_argument("--player", default=None, help="запускать собранный плеер вместо редактора")
    group.add_argument("--close-unity", action="store_true", help="закрыть Unity после завершения скрипта")


def ensure_scene(args) -> Any:
    """Запускает Unity со сценой по аргументам командной строки (если она еще не работает)."""
    from scene.launcher import UnityLaunchError, launch_unity

    if args.no_launch:
        return None
    try:
        return launch_unity(scene=args.scene, host=args.host, port=args.port, unity=args.unity, player=args.player)
    except UnityLaunchError as e:
        raise SystemExit(f"Не удалось запустить сцену: {e}") from None


def connect(argv: list[str] | None = None, description: str | None = None) -> Simulation:
    """
    Simulation по аргументам командной строки скрипта.

    По умолчанию, если сцена не отвечает, запускает Unity с проектом, открывает
    сцену 1 (Assets/1.unity) в режиме управления из Python и нажимает Play. --offline — встроенная модель без Unity,
    --no-launch — только подключиться к уже запущенной сцене.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--offline", action="store_true", help="без Unity, на встроенной модели сцены")
    parser.add_argument("-v", "--verbose", action="store_true")
    add_connection_args(parser)
    args, _ = parser.parse_known_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    if args.offline:
        log.info("Офлайн-режим: встроенная модель сцены")
        return Simulation.offline()

    unity = ensure_scene(args)
    sim = Simulation(host=args.host, port=args.port, unity=unity, close_unity=args.close_unity)
    if not sim.is_connected():
        log.warning("RSMA не отвечает на %s:%d — запущена ли сцена в Unity?", args.host, args.port)
    else:
        sim.wait_for_scene()
    return sim
