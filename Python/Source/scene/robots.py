import logging
import math
from collections.abc import Iterable

from RSMA.Mathf import clamp, delta_angle
from RSMA.Time import get_unix_time_milliseconds
from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP.Topics import MotorInput, Pose, RobotVelocity

log = logging.getLogger("scene")

# Уровни внешнего управления (Assets/Scripts/uDTP/ExternalControl.cs)
COMMANDS = 1
ACTUATORS = 2


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


class Maruz:
    """
    Колесный робот Maruz (сцена SupremeFlat): дифференциальный привод.

        maruz = sim.maruz()
        maruz.drive(0.5, duration=2)      # 0.5 м/с вперед 2 секунды
        maruz.turn(0.8, duration=1)       # поворот влево 0.8 рад/с
        maruz.go_to(3, 4)                 # в точку (x=3, z=4) по земле

    Пока скрипт командует роботом, встроенные контроллеры Maruz в Unity
    (MaruzVelocity, MaruzPositionController, MaruzTrajectoryPlanner) молчат.
    release() возвращает им управление.

    heading — направление движения робота: рыскание в градусах, как в Unity
    (0 — вдоль +Z, 90 — вдоль +X). Положительная угловая скорость — поворот влево.
    """

    def __init__(self, sim, name: str = "Maruz"):
        self.sim = sim
        self.name = name

    def __repr__(self) -> str:
        return f"Maruz({self.name!r}, position={self.position}, heading={self.heading})"

    @property
    def pose(self) -> Pose | None:
        return self.sim.get(f"{self.name}Pose", Pose)

    @property
    def position(self) -> Vector3 | None:
        pose = self.pose
        return None if pose is None else pose.position

    @property
    def heading(self) -> float | None:
        pose = self.pose
        return None if pose is None else pose.rotation.to_yaw()

    # --- Прямые команды ---

    def drive(self, linear: float, angular: float = 0.0, duration: float | None = None) -> None:
        """
        Задает скорость: linear — м/с (вперед > 0), angular — рад/с (влево > 0).
        С duration — едет указанное время и останавливается.
        """
        command = RobotVelocity(timestamp=get_unix_time_milliseconds(),
                                linearVelocity=float(linear), angularVelocity=float(angular))
        self.sim.take_control(self.name, COMMANDS, [(f"{self.name}TargetVelocity", command)])
        if duration is not None:
            self.sim.sleep(duration)
            self.stop()

    def turn(self, angular: float, duration: float | None = None) -> None:
        """Поворот на месте с угловой скоростью angular (рад/с, влево > 0)."""
        self.drive(0.0, angular, duration)

    def set_wheels(self, left: float, right: float, duration: float | None = None) -> None:
        """Прямое управление моторами колес, значения от -1 до 1 (MaruzML / MaruzMR)."""
        ts = get_unix_time_milliseconds()
        self.sim.take_control(self.name, ACTUATORS, [
            (f"{self.name}ML", MotorInput(timestamp=ts, input=clamp(float(left), -1.0, 1.0))),
            (f"{self.name}MR", MotorInput(timestamp=ts, input=clamp(float(right), -1.0, 1.0))),
        ])
        if duration is not None:
            self.sim.sleep(duration)
            self.stop()

    def stop(self) -> None:
        """Остановка (управление остается у скрипта)."""
        self.drive(0.0, 0.0)

    def release(self) -> None:
        """Остановиться и вернуть управление Unity-контроллерам робота."""
        self.stop()
        self.sim.release_control(self.name)

    # --- Навигация ---

    def _require_pose(self) -> Pose:
        pose = self.pose
        if pose is None:
            raise RuntimeError(f"Поза робота неизвестна: топик {self.name}Pose не публикуется")
        return pose

    def rotate_to(self, heading: float, tolerance: float = 3.0, max_angular: float = 1.5, k: float = 2.0,
                  timeout: float | None = 20.0, period: float = 0.05) -> bool:
        """Поворот на месте до направления heading (градусы, как в Unity)."""
        start = self.sim.time
        while True:
            error = delta_angle(self._require_pose().rotation.to_yaw(), heading)
            if abs(error) <= tolerance:
                self.stop()
                return True
            if timeout is not None and self.sim.time - start >= timeout:
                self.stop()
                log.warning("%s: не удалось повернуть на %.1f° за %s с", self.name, heading, timeout)
                return False
            # Ошибка > 0 — цель правее, нужно увеличить рыскание, т.е. повернуть вправо (angular < 0)
            self.drive(0.0, -clamp(k * math.radians(error), -max_angular, max_angular))
            self.sim.sleep(period)

    def go_to(self, x: float, z: float, speed: float = 0.5, tolerance: float = 0.35,
              max_angular: float = 1.5, k: float = 2.0, timeout: float | None = 60.0, period: float = 0.05,
              stop: bool = True) -> bool:
        """
        Едет в точку (x, z) на плоскости земли: поворачивает на цель и едет,
        замедляясь при большой ошибке курса (> 60° — разворот на месте).
        Возвращает True, если доехал в пределах tolerance м.
        """
        start = self.sim.time
        while True:
            pose = self._require_pose()
            dx, dz = x - pose.position.x, z - pose.position.z
            distance = math.hypot(dx, dz)
            if distance <= tolerance:
                if stop:
                    self.stop()
                return True
            if timeout is not None and self.sim.time - start >= timeout:
                self.stop()
                log.warning("%s: не доехал до (%.2f, %.2f) за %s с, осталось %.2f м", self.name, x, z, timeout, distance)
                return False

            bearing = math.degrees(math.atan2(dx, dz))
            error = delta_angle(pose.rotation.to_yaw(), bearing)
            angular = -clamp(k * math.radians(error), -max_angular, max_angular)
            linear = 0.0 if abs(error) > 60.0 else speed * max(0.0, math.cos(math.radians(error)))
            # Плавное торможение у цели
            linear = min(linear, max(0.1, distance))
            self.drive(linear, angular)
            self.sim.sleep(period)

    def follow(self, points: Iterable, **kwargs) -> bool:
        """Проезжает точки (x, z) по очереди. Возвращает False на первой недостигнутой."""
        points = list(points)
        for i, (x, z) in enumerate(points):
            last = i == len(points) - 1
            if not self.go_to(x, z, stop=last, **kwargs):
                return False
        return True
