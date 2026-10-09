import logging
import math

from RSMA.Time import get_unix_time_milliseconds
from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP.Topics import Pose

log = logging.getLogger("scene")


def _vec(x, y=None, z=None) -> Vector3:
    """Vector3 из (x, y, z), кортежа/списка или Vector3."""
    if y is None and z is None:
        if isinstance(x, Vector3):
            return Vector3(x.x, x.y, x.z)
        x, y, z = x
    return Vector3(float(x), float(y), float(z))


class Drone:
    """
    Квадрокоптер Quadrocopter.cs: летит в заданную точку своим PID-регулятором.

        drone = sim.drone(1)
        drone.fly_to(0, 5, 10)        # координаты Unity, Y — высота
        print(drone.position)
    """

    def __init__(self, sim, drone_id: int = 1):
        self.sim = sim
        self.id = drone_id
        self.target: Vector3 | None = None

    def __repr__(self) -> str:
        return f"Drone({self.id}, position={self.position})"

    @property
    def pose(self) -> Pose | None:
        return self.sim.get(f"DronePose_{self.id}", Pose)

    @property
    def position(self) -> Vector3 | None:
        pose = self.pose
        return None if pose is None else pose.position

    @property
    def cable_force(self) -> float | None:
        """Натяжение троса этого дрона, Н (если дрон привязан к грузу)."""
        return self.sim.cable_force(self.id)

    def set_target(self, x, y=None, z=None) -> Vector3:
        """Задает целевую точку и сразу возвращается (не ждет прилета)."""
        target = _vec(x, y, z)
        if target.sqr_magnitude() < 1e-8:
            # Quadrocopter.cs игнорирует цель (0, 0, 0)
            log.warning("Цель (0, 0, 0) дрон игнорирует, используется (0, 0.01, 0)")
            target = Vector3(0.0, 0.01, 0.0)
        self.target = target
        self.sim.publish(f"DroneTargetPose_{self.id}",
                         Pose(target, Quaternion.identity(), get_unix_time_milliseconds()))
        return target

    def distance_to_target(self) -> float | None:
        pos = self.position
        if pos is None or self.target is None:
            return None
        return pos.distance_to(self.target)

    def fly_to(self, x, y=None, z=None, tolerance: float = 0.3, timeout: float | None = 60.0,
               wait: bool = True) -> bool:
        """Летит в точку. С wait=True ждет прилета (в пределах tolerance м), возвращает успех."""
        self.set_target(x, y, z)
        if not wait:
            return True
        ok = self.sim.wait_until(lambda: (self.distance_to_target() or math.inf) <= tolerance, timeout)
        if not ok:
            log.warning("Дрон %d не долетел до %s за %s с (позиция %s)", self.id, self.target, timeout, self.position)
        return ok

    def move_by(self, dx: float, dy: float, dz: float, **kwargs) -> bool:
        """Смещение относительно текущей позиции (или последней цели)."""
        base = self.position or self.target
        if base is None:
            raise RuntimeError(f"Позиция дрона {self.id} неизвестна: DronePose_{self.id} не публикуется")
        return self.fly_to(base.x + dx, base.y + dy, base.z + dz, **kwargs)

    def hover(self) -> None:
        """Зависнуть в текущей точке."""
        pos = self.position
        if pos is not None:
            self.set_target(pos)

    def land(self, ground_y: float = 0.2, **kwargs) -> bool:
        """Снижение по вертикали до высоты ground_y."""
        pos = self.position or self.target
        if pos is None:
            raise RuntimeError(f"Позиция дрона {self.id} неизвестна")
        return self.fly_to(pos.x, ground_y, pos.z, **kwargs)


class Swarm:
    """
    Рой дронов, несущий груз на тросах (сцена RSMASwarmEnvironment).

    Формация запоминается при создании: смещения дронов от груза по горизонтали.
    Команды задают положение *груза*, а дроны держат формацию над ним.

        swarm = sim.swarm()
        swarm.lift(3.0)                       # поднять груз на 3 м
        swarm.move_payload_by(10, 0, 5)       # перенести груз
        swarm.lower()                         # опустить груз
        swarm.land()                          # посадить дронов
    """

    def __init__(self, sim, drone_ids: list[int] | None = None, cable_length: float = 2.0,
                 cable_margin: float = 0.2):
        self.sim = sim
        if drone_ids is None:
            drone_ids = sim.find_drones()
        self.drones = [Drone(sim, i) for i in drone_ids]
        if not self.drones:
            raise RuntimeError("В сцене нет дронов (топики DronePose_i)")

        payload = sim.payload_pose()
        if payload is None:
            raise RuntimeError("Груз не найден: топик PayloadPose не публикуется")
        self.ground_y = payload.position.y  # высота центра груза, стоящего на земле

        # Формация: горизонтальные смещения дронов от груза
        self.offsets: dict[int, tuple[float, float]] = {}
        for d in self.drones:
            pos = d.position
            if pos is None:
                raise RuntimeError(f"Позиция дрона {d.id} неизвестна")
            self.offsets[d.id] = (pos.x - payload.position.x, pos.z - payload.position.z)

        radius = max(math.hypot(*off) for off in self.offsets.values())
        # Высота дронов над грузом при натянутых тросах
        self.hang_height = math.sqrt(max(0.1, cable_length**2 - radius**2)) + cable_margin
        self.payload_target: Vector3 | None = None

    def __repr__(self) -> str:
        return f"Swarm(drones={[d.id for d in self.drones]}, payload={self.payload_position})"

    @property
    def payload_position(self) -> Vector3 | None:
        pose = self.sim.payload_pose()
        return None if pose is None else pose.position

    def cable_forces(self) -> dict[int, float | None]:
        return {d.id: d.cable_force for d in self.drones}

    def set_payload_target(self, x, y=None, z=None) -> None:
        """Ставит дронам цели так, чтобы груз висел в точке (x, y, z). Не ждет."""
        target = _vec(x, y, z)
        self.payload_target = target
        for d in self.drones:
            ox, oz = self.offsets[d.id]
            d.set_target(target.x + ox, target.y + self.hang_height, target.z + oz)

    def move_payload_to(self, x, y=None, z=None, speed: float = 0.6, tolerance: float = 0.4,
                        timeout: float | None = 120.0, period: float = 0.05) -> bool:
        """
        Плавно переносит груз в точку: цель движется со скоростью speed (м/с),
        затем ждет, пока груз окажется ближе tolerance м. Возвращает успех.
        """
        goal = _vec(x, y, z)
        start = self.payload_target or self.payload_position
        if start is None:
            raise RuntimeError("Позиция груза неизвестна")

        distance = start.distance_to(goal)
        steps = max(1, math.ceil(distance / (speed * period)))
        for k in range(1, steps + 1):
            self.set_payload_target(start.lerp(goal, k / steps))
            self.sim.sleep(period)

        ok = self.sim.wait_until(
            lambda: (p := self.payload_position) is not None and p.distance_to(goal) <= tolerance, timeout)
        if not ok:
            log.warning("Груз не дошел до %s за %s с (сейчас %s)", goal, timeout, self.payload_position)
        return ok

    def move_payload_by(self, dx: float, dy: float, dz: float, **kwargs) -> bool:
        base = self.payload_target or self.payload_position
        return self.move_payload_to(base.x + dx, base.y + dy, base.z + dz, **kwargs)

    def lift(self, height: float = 3.0, **kwargs) -> bool:
        """Поднимает груз на height м над землей."""
        p = self.payload_target or self.payload_position
        return self.move_payload_to(p.x, self.ground_y + height, p.z, **kwargs)

    def lower(self, settle_time: float = 1.0, **kwargs) -> bool:
        """Опускает груз на землю под текущей точкой и дает ему успокоиться settle_time с."""
        p = self.payload_target or self.payload_position
        kwargs.setdefault("tolerance", 0.3)
        ok = self.move_payload_to(p.x, self.ground_y, p.z, **kwargs)
        self.sim.sleep(settle_time)
        return ok

    def land(self, ground_y: float | None = None, timeout: float | None = 60.0) -> bool:
        """
        Сажает дронов в точки формации вокруг груза (тросы провисают).
        Дроны снижаются строго по вертикали над своими местами в строю, чтобы не тянуть груз.
        """
        y = self.ground_y if ground_y is None else ground_y
        center = self.payload_target or self.payload_position
        for d in self.drones:
            ox, oz = self.offsets[d.id]
            d.set_target(center.x + ox, y, center.z + oz)
        return self.sim.wait_until(lambda: all((d.distance_to_target() or math.inf) <= 0.3 for d in self.drones),
                                   timeout)
