"""
Упрощенная физическая модель сцены доставки груза роем — замена Unity для
отладки и тестов контура управления без запуска RSMA.

Модель повторяет компоненты сцены:
* дрон — Quadrocopter.cs: PID по позиции + компенсация веса, ограничение силы,
  линейное демпфирование Rigidbody;
* трос — RSMACable.cs: пружина-демпфер, работает только на растяжение;
* груз — Payload.prefab: точечная масса 12 кг, контакт с землей.

Обмен идет через те же топики uDTP и в координатах Unity (Y — вверх),
поэтому контроллер работает с моделью так же, как с настоящей сценой.
"""

from dataclasses import dataclass

import numpy as np

from RSMA.Broker import InMemoryBroker
from RSMA.Types.Quaternion import Quaternion
from RSMA.uDTP.Topics.Float32 import Float32
from RSMA.uDTP.Topics.Pose import Pose
from utils.rsma_helpers import py_to_unity_v3, unity_to_py_v3

GRAVITY = 9.81


@dataclass
class DroneParams:  # Quadrocopter.cs
    mass: float = 2.5
    max_force: float = 250.0
    kp: float = 8.0
    ki: float = 2.0
    kd: float = 2.0
    linear_damping: float = 0.8
    ground_z: float = 0.1


@dataclass
class CableParams:  # RSMACable.cs
    rest_length: float = 2.0
    stiffness: float = 1000.0
    damping: float = 35.0
    max_force: float = 200.0


@dataclass
class PayloadParams:  # Payload.prefab
    mass: float = 12.0
    ground_z: float = 0.25  # высота центра масс груза, стоящего на земле
    air_drag: float = 0.05
    ground_friction: float = 8.0


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
        """Дроны стоят на земле вокруг груза в точках формации."""
        payload_pos = np.asarray(payload_pos, dtype=float)
        ground = (kwargs.get("drone") or DroneParams()).ground_z
        positions = {i: np.array([payload_pos[0] + off[0], payload_pos[1] + off[1], ground])
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
        payload_force = np.array([0.0, 0.0, -p.mass * GRAVITY]) + self.wind - p.air_drag * self.payload_vel

        for i in self.ids:
            f_cable = self._cable(i)
            payload_force += f_cable

            force = np.array([0.0, 0.0, -d.mass * GRAVITY]) - f_cable
            target = self.drone_target[i]
            if target is not None:
                err = target - self.drone_pos[i]
                self.drone_int[i] += err * h
                ctrl = err * d.kp + self.drone_int[i] * d.ki - self.drone_vel[i] * d.kd
                ctrl[2] += d.mass * GRAVITY
                norm = float(np.linalg.norm(ctrl))
                if norm > d.max_force:
                    ctrl *= d.max_force / norm
                force += ctrl

            vel = self.drone_vel[i] + force / d.mass * h
            vel /= 1.0 + d.linear_damping * h
            pos = self.drone_pos[i] + vel * h
            if pos[2] < d.ground_z:
                pos[2] = d.ground_z
                vel = np.array([0.0, 0.0, max(vel[2], 0.0)])
            self.drone_vel[i], self.drone_pos[i] = vel, pos

        vel = self.payload_vel + payload_force / p.mass * h
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
