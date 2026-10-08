"""
Офлайн-модель сцены для Python-скриптов управления (scene.Simulation.offline()).

Публикует те же топики, что Unity, и читает те же команды:
* дроны Quadrocopter.cs: DronePose_i <- DroneTargetPose_i;
* робот Maruz (Maruz.cs + MotionController.cs): MaruzPose <- MaruzTargetVelocity,
  а при аренде уровня 2 (ExternalControl.Actuators) <- MaruzML / MaruzMR;
* статичные датчики: лидар (все лучи = rangeMax), дальномер.

Координаты Unity (Y — вверх). Модель не заменяет Unity (нет препятствий,
коллизий и проскальзывания), но позволяет отладить логику скрипта.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from RSMA.Broker import InMemoryBroker
from RSMA.Types.Quaternion import Quaternion
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP.Topics import ControlLease, Float32, LaserScan128, MotorInput, Pose, RobotVelocity
from sim.swarm_sim import DroneParams, drone_step
from utils.rsma_helpers import py_to_unity_v3, unity_to_py_v3


@dataclass
class MaruzParams:  # MotionController.cs в сцене SupremeFlat
    wheel_base: float = 0.8
    wheel_radius: float = 0.1
    max_wheel_deg: float = 3600.0


@dataclass
class _Drone:
    pos: np.ndarray  # Python, Z — вверх
    vel: np.ndarray = field(default_factory=lambda: np.zeros(3))
    integral: np.ndarray = field(default_factory=lambda: np.zeros(3))
    target: np.ndarray | None = None


class OfflineScene:
    def __init__(self, broker: InMemoryBroker, drones: dict[int, tuple] | None = None,
                 maruz: tuple | None = (0.0, 0.0, 0.0), maruz_heading: float = 0.0,
                 lidar_topic: str | None = "Lidar", rangefinder_topic: str | None = "RangeFinder",
                 dt: float = 0.01):
        """drones: {id: (x, y, z)} и maruz: (x, y, z) — начальные позиции в координатах Unity."""
        self.broker = broker
        self.dt = dt
        self.time = 0.0
        self.drone_params = DroneParams()
        self.maruz_params = MaruzParams()

        if drones is None:
            drones = {1: (0.0, 0.1, 3.0)}
        self.drones = {i: _Drone(unity_to_py_v3(Vector3(*p))) for i, p in drones.items()}

        self.maruz_pos = None if maruz is None else np.array(maruz, dtype=float)
        self.maruz_heading = maruz_heading  # рыскание направления движения, градусы (как в Unity)

        self.lidar_topic = lidar_topic
        self.rangefinder_topic = rangefinder_topic
        self._publish()

    def _timestamp(self) -> int:
        return 1 + int(self.time * 1000)

    # --- Команды ---

    def _maruz_velocity(self) -> tuple[float, float]:
        """(linear м/с, angular рад/с) — как их исполняют MotionController и Maruz."""
        lease = self.broker.get_obj("ExternalControl_Maruz", ControlLease)
        p = self.maruz_params
        if lease.level >= 2:
            max_rad = math.radians(p.max_wheel_deg)
            left = self.broker.get_obj("MaruzML", MotorInput).input
            right = self.broker.get_obj("MaruzMR", MotorInput).input
            v_l = max(-1.0, min(1.0, left)) * max_rad * p.wheel_radius
            v_r = max(-1.0, min(1.0, right)) * max_rad * p.wheel_radius
            return (v_l + v_r) / 2.0, (v_r - v_l) / p.wheel_base
        cmd = self.broker.get_obj("MaruzTargetVelocity", RobotVelocity)
        return cmd.linearVelocity, cmd.angularVelocity

    # --- Шаг модели ---

    def step(self) -> None:
        h = self.dt
        for i, d in self.drones.items():
            target = unity_to_py_v3(self.broker.get_obj(f"DroneTargetPose_{i}", Pose).position)
            if np.any(target != 0.0):  # Quadrocopter.cs игнорирует нулевую цель
                d.target = target
            d.pos, d.vel, d.integral = drone_step(d.pos, d.vel, d.integral, d.target, self.drone_params, h)

        if self.maruz_pos is not None:
            linear, angular = self._maruz_velocity()
            # Положительная угловая скорость — поворот влево (рыскание Unity уменьшается)
            self.maruz_heading -= math.degrees(angular) * h
            yaw = math.radians(self.maruz_heading)
            self.maruz_pos += np.array([math.sin(yaw), 0.0, math.cos(yaw)]) * linear * h

        self.time += h
        self._publish()

    def advance(self, seconds: float) -> None:
        for _ in range(max(1, round(seconds / self.dt))):
            self.step()

    def _publish(self) -> None:
        ts = self._timestamp()
        for i, d in self.drones.items():
            self.broker.publish_obj(f"DronePose_{i}", Pose(py_to_unity_v3(d.pos), Quaternion.identity(), ts))
        if self.maruz_pos is not None:
            self.broker.publish_obj("MaruzPose", Pose(Vector3(*self.maruz_pos),
                                                      Quaternion.euler(0.0, self.maruz_heading, 0.0), ts))
        if self.lidar_topic:
            n = 128
            self.broker.publish_obj(self.lidar_topic, LaserScan128(
                ranges=[20.0] * n, angleMin=0.5, angleMax=360.0, angleIncrement=(360.0 - 0.5) / (n - 1),
                rangeMin=0.05, rangeMax=20.0, timestamp=ts))
        if self.rangefinder_topic:
            self.broker.publish_obj(self.rangefinder_topic, Float32(value=4.0, timestamp=ts))
