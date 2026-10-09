"""
Упрощенная физическая модель сцены доставки груза роем — замена Unity для
отладки и тестов контура управления без запуска RSMA.

Модель повторяет компоненты сцены:
* дрон — Quadrocopter.cs: PID по позиции + компенсация веса, ограничение силы,
  линейное демпфирование Rigidbody;
* трос — RSMACable.cs: пружина-демпфер, работает только на растяжение;
* груз — Payload.prefab: точечная масса 12 кг, демпфирование, контакт с землей;
* начальная расстановка — RSMASwarmEnvironment.cs: дроны в точках формации
  на 0.2 м выше груза.

Обмен идет через те же топики uDTP и в координатах Unity (Y — вверх),
поэтому контроллер работает с моделью так же, как с настоящей сценой.
"""

import math
from dataclasses import dataclass

import numpy as np

from RSMA.Broker import InMemoryBroker
from RSMA.Types.Quaternion import Quaternion
from RSMA.uDTP.Topics.Float32 import Float32
from RSMA.uDTP.Topics.Pose import Pose
from utils.rsma_helpers import py_to_unity_v3, unity_to_py_v3

GRAVITY = 9.81


@dataclass
class DroneParams:  # Quadrocopter.cs; PID — SwarmDeliveryScene.external* (сцена 1 под управлением Python)
    mass: float = 2.5
    max_force: float = 250.0
    max_integral_force: float = 250.0
    kp: float = 10.0
    ki: float = 2.0
    kd: float = 12.0
    linear_damping: float = 0.8
    ground_z: float = 0.1


@dataclass
class CableParams:  # RSMACable.cs, значения из RSMASwarmEnvironment.cs
    rest_length: float = 2.0
    stiffness: float = 1000.0
    damping: float = 35.0
    max_force: float = 250.0


@dataclass
class PayloadParams:  # Payload.prefab / RSMASwarmEnvironment.cs
    mass: float = 12.0
    ground_z: float = 0.25  # высота центра масс груза, стоящего на земле
    linear_damping: float = 0.2  # Rigidbody.linearDamping
    ground_friction: float = 8.0


def drone_step(pos: np.ndarray, vel: np.ndarray, integral: np.ndarray, target: np.ndarray | None,
               d: DroneParams, h: float, external_force: np.ndarray | None = None
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Один шаг дрона Quadrocopter.cs (система Python, Z — вверх).
    Возвращает новые (pos, vel, integral). Без цели дрон не управляется (isControlledByApi = false).
    """
    force = np.array([0.0, 0.0, -d.mass * GRAVITY])
    if external_force is not None:
        force = force + external_force
    if target is not None:
        err = target - pos
        integral = integral + err * h
        if d.ki > 0:  # анти-windup: вклад интеграла не больше max_integral_force
            i_force = integral * d.ki
            norm = float(np.linalg.norm(i_force))
            if norm > d.max_integral_force:
                integral = i_force * (d.max_integral_force / norm) / d.ki
        ctrl = err * d.kp + integral * d.ki - vel * d.kd
        ctrl[2] += d.mass * GRAVITY
        # Ограничение силы с приоритетом вертикали: горизонталь получает только остаток
        vertical = float(np.clip(ctrl[2], -d.max_force, d.max_force))
        horizontal = ctrl[:2]
        h_limit = math.sqrt(max(0.0, d.max_force**2 - vertical**2))
        h_norm = float(np.linalg.norm(horizontal))
        if h_norm > h_limit:
            horizontal = horizontal * (h_limit / h_norm)
        force = force + np.array([horizontal[0], horizontal[1], vertical])

    vel = (vel + force / d.mass * h) / (1.0 + d.linear_damping * h)
    pos = pos + vel * h
    if pos[2] < d.ground_z:
        pos[2] = d.ground_z
        vel = np.array([0.0, 0.0, max(vel[2], 0.0)])
    return pos, vel, integral


class SwarmPhysicsSim:
    def __init__(self, broker: InMemoryBroker, drone_positions: dict[int, np.ndarray], payload_pos,
                 drone: DroneParams | None = None, cable: CableParams | None = None,
                 payload: PayloadParams | None = None, substeps: int = 4,
                 wind: np.ndarray | None = None):
        """
        drone_positions, payload_pos — начальные позиции в системе Python (Z — вверх).
        wind — постоянная внешняя сила на груз [Fx, Fy, Fz] (Н), для проверки anti-sway.
        """
        self.broker = broker
        self.drone = drone or DroneParams()
        self.cable = cable or CableParams()
        self.payload = payload or PayloadParams()
        self.substeps = max(1, substeps)
        self.wind = np.zeros(3) if wind is None else np.asarray(wind, dtype=float)

        self.ids = sorted(drone_positions)
        self.drone_pos = {i: np.array(p, dtype=float) for i, p in drone_positions.items()}
        self.drone_vel = {i: np.zeros(3) for i in self.ids}
        self.drone_int = {i: np.zeros(3) for i in self.ids}
        self.drone_target: dict[int, np.ndarray | None] = {i: None for i in self.ids}
        self.cable_force = {i: 0.0 for i in self.ids}

        self.payload_pos = np.array(payload_pos, dtype=float)
        self.payload_vel = np.zeros(3)
        self.time = 0.0

        self._publish()

    @classmethod
    def around_payload(cls, broker: InMemoryBroker, payload_pos, offsets: dict[int, np.ndarray], **kwargs):
        """Дроны в точках формации на 0.2 м выше груза, как в RSMASwarmEnvironment.BuildSwarmScene()."""
        payload_pos = np.asarray(payload_pos, dtype=float)
        # Земля — под стартовой точкой груза (в сцене 1 база стоит на рельефе)
        kwargs.setdefault("payload", PayloadParams(ground_z=float(payload_pos[2])))
        kwargs.setdefault("drone", DroneParams(ground_z=float(payload_pos[2]) - 0.15))
        positions = {i: np.array([payload_pos[0] + off[0], payload_pos[1] + off[1], payload_pos[2] + 0.2])
                     for i, off in offsets.items()}
        return cls(broker, positions, payload_pos, **kwargs)

    # --- Обмен с брокером ---

    def _timestamp(self) -> int:
        return 1 + int(self.time * 1000)  # не 0: иначе is_published() считает топик пустым

    def _publish(self) -> None:
        ts = self._timestamp()
        for i in self.ids:
            self.broker.publish_obj(f"DronePose_{i}", Pose(py_to_unity_v3(self.drone_pos[i]), Quaternion.identity(), ts))
            self.broker.publish_obj(f"CableForce_{i}", Float32(value=self.cable_force[i], timestamp=ts))
        self.broker.publish_obj("PayloadPose", Pose(py_to_unity_v3(self.payload_pos), Quaternion.identity(), ts))

    def _read_targets(self) -> None:
        for i in self.ids:
            msg = self.broker.get_obj(f"DroneTargetPose_{i}", Pose)
            target = unity_to_py_v3(msg.position)
            # Quadrocopter.cs игнорирует нулевую цель
            if np.any(target != 0.0):
                self.drone_target[i] = target

    # --- Физика ---

    def _cable(self, i: int) -> np.ndarray:
        """Сила троса, действующая на груз (на дрон — с обратным знаком)."""
        delta = self.drone_pos[i] - self.payload_pos
        dist = float(np.linalg.norm(delta))
        c = self.cable
        if dist <= c.rest_length or dist < 1e-9:
            self.cable_force[i] = 0.0
            return np.zeros(3)
        direction = delta / dist
        v_rel = float(np.dot(self.drone_vel[i] - self.payload_vel, direction))
        force = min(max(c.stiffness * (dist - c.rest_length) + c.damping * v_rel, 0.0), c.max_force)
        self.cable_force[i] = force
        return direction * force

    def _substep(self, h: float) -> None:
        d, p = self.drone, self.payload
        payload_force = np.array([0.0, 0.0, -p.mass * GRAVITY]) + self.wind

        for i in self.ids:
            f_cable = self._cable(i)
            payload_force += f_cable

            self.drone_pos[i], self.drone_vel[i], self.drone_int[i] = drone_step(
                self.drone_pos[i], self.drone_vel[i], self.drone_int[i], self.drone_target[i], d, h,
                external_force=-f_cable)

        vel = self.payload_vel + payload_force / p.mass * h
        vel /= 1.0 + p.linear_damping * h
        pos = self.payload_pos + vel * h
        if pos[2] <= p.ground_z:
            pos[2] = p.ground_z
            vel[2] = max(vel[2], 0.0)
            vel[:2] /= 1.0 + p.ground_friction * h
        self.payload_vel, self.payload_pos = vel, pos

    def step(self, dt: float) -> None:
        """Продвигает модель на dt секунд и публикует новую телеметрию."""
        if dt <= 0:
            return
        self._read_targets()
        h = dt / self.substeps
        for _ in range(self.substeps):
            self._substep(h)
        self.time += dt
        self._publish()
