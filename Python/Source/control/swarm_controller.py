# control/swarm_controller.py

import logging
import math
import time
from collections.abc import Callable

import numpy as np

import config as default_config
from control.anti_sway import AntiSwayController
from control.flight_state_machine import FlightStateMachine, SwarmFlightPhase
from control.formation import FormationManager
from control.trajectory import JerkLimitedTrajectory
from RSMA.Time import get_unix_time_milliseconds
from RSMA.Types.Quaternion import Quaternion
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics.Float32 import Float32
from RSMA.uDTP.Topics.Pose import Pose
from utils.logger import CSVLogger, TelemetryLogger
from utils.rsma_helpers import py_to_unity_v3, unity_to_py_v3

log = logging.getLogger("swarm")

PAYLOAD_TOPIC = "PayloadPose"


def drone_pose_topic(d_id: int) -> str:
    return f"DronePose_{d_id}"


def drone_target_topic(d_id: int) -> str:
    return f"DroneTargetPose_{d_id}"


def cable_force_topic(d_id: int) -> str:
    return f"CableForce_{d_id}"


class SwarmRSMAController:
    """
    Контур управления роем: читает телеметрию из RSMA, ведет автомат состояний
    миссии и публикует целевые позиции дронов (DroneTargetPose_i).

    client — RSMAClient (реальный Unity) или RSMA.Broker.LocalClient (симуляция/тесты).
    config — модуль или объект с параметрами (см. config.py).
    """

    def __init__(self, client=None, config=default_config, csv_log: bool = True):
        self.cfg = config
        self.num_drones: int = self._param("NUM_DRONES", 6)
        self.formation_radius: float = self._param("FORMATION_RADIUS", 1.414)
        self.cable_length: float = self._param("CABLE_LENGTH", 2.0)
        self.dt: float = self._param("DT", 0.01)
        self.use_anti_sway: bool = self._param("USE_ANTI_SWAY", True)
        self.csv_log = csv_log

        self.formation = FormationManager(num_drones=self.num_drones, radius=self.formation_radius)
        self.offsets = self.formation.get_formation_offsets()

        self.anti_sways = {
            d_id: AntiSwayController(
                k_sway=self._param("K_SWAY", 1.5),
                d_sway=self._param("D_SWAY", 0.5),
                max_correction=self._param("MAX_SWAY_CORRECTION", None),
            )
            for d_id in range(1, self.num_drones + 1)
        }

        if client is None:
            from RSMA.Client import RSMAClient

            host = self._param("RSMA_HOST", "localhost")
            port = self._param("RSMA_PORT", 5555)
            log.info("Подключение к RSMA Broker tcp://%s:%s ...", host, port)
            client = RSMAClient(host=host, port=port, timeout=self._param("RSMA_TIMEOUT_MS", 1000))
        self.client = client

        # Состояние миссии (заполняется в start_mission)
        self.fsm: FlightStateMachine | None = None
        self.traj: JerkLimitedTrajectory | None = None
        self.csv_logger: CSVLogger | None = None
        self.start_pos: np.ndarray | None = None
        self.payload_pos: np.ndarray | None = None
        self.step_count = 0
        self._sway_active = False

    def _param(self, name: str, default):
        return getattr(self.cfg, name, default)

    @property
    def hang_height(self) -> float:
        """Высота дронов над грузом при натянутых тросах (+ запас)."""
        vertical = math.sqrt(max(0.1, self.cable_length**2 - self.formation_radius**2))
        return vertical + self._param("CABLE_MARGIN", 0.2)

    # --- Телеметрия ---

    def read_payload_position(self) -> np.ndarray | None:
        pose = self.client.get_state(PAYLOAD_TOPIC, Pose)
        return unity_to_py_v3(pose.position) if is_published(pose) else None

    def read_drone_position(self, d_id: int) -> np.ndarray | None:
        pose = self.client.get_state(drone_pose_topic(d_id), Pose)
        return unity_to_py_v3(pose.position) if is_published(pose) else None

    def get_cables_forces(self) -> dict[int, float]:
        """Считывает силы натяжения каждого троса."""
        forces = {}
        for d_id in range(1, self.num_drones + 1):
            msg = self.client.get_state(cable_force_topic(d_id), Float32)
            forces[d_id] = float(msg.value) if msg is not None else 0.0
        return forces

    def wait_for_payload(self, timeout: float | None = None, poll_interval: float = 0.02) -> np.ndarray | None:
        """Ждет первую телеметрию груза. Возвращает позицию или None по таймауту."""
        log.info("Ожидание первой телеметрии груза (%s) из RSMA...", PAYLOAD_TOPIC)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            pos = self.read_payload_position()
            if pos is not None:
                return pos
            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval)

    # --- Миссия ---

    def start_mission(self, payload_pos) -> None:
        self.start_pos = np.array(payload_pos, dtype=float)
        self.payload_pos = self.start_pos.copy()

        finish_xy = self.start_pos[:2] + np.array([
            self._param("TARGET_OFFSET_X", 15.0),
            self._param("TARGET_OFFSET_Y", 8.0),
        ])
        flight_z = self._param("CRUISE_ALTITUDE", 3.0)

        self.fsm = FlightStateMachine(
            start_pos=self.start_pos,
            finish_xy=finish_xy,
            target_flight_z=flight_z,
            target_land_z=self._param("LAND_ALTITUDE", 0.5),
            climb_rate=self._param("CLIMB_RATE", 0.6),
            hang_height=self.hang_height,
            drone_land_z=self._param("DRONE_LAND_ALTITUDE", 0.25),
            hover_time=self._param("HOVER_TIME", 2.0),
            lift_tolerance=self._param("LIFT_TOLERANCE", 0.35),
            land_tolerance=self._param("LAND_TOLERANCE", 0.05),
            land_settle_time=self._param("LAND_SETTLE_TIME", 3.0),
            finish_tolerance=self._param("FINISH_TOLERANCE", 0.3),
        )
        self.traj = JerkLimitedTrajectory(
            start_pos=[self.start_pos[0], self.start_pos[1], flight_z],
            target_pos=[finish_xy[0], finish_xy[1], flight_z],
            v_max=self._param("V_MAX", 0.8),
            a_max=self._param("A_MAX", 1.0),
            j_max=self._param("J_MAX", 2.0),
        )
        if self.csv_log:
            self.csv_logger = CSVLogger(num_drones=self.num_drones, log_dir=self._param("LOG_DIR", "logs"))
        self.step_count = 0
        self._sway_active = False

        log.info("Старт миссии! Исходная позиция груза: %s, точка доставки: %s. Фаза: LIFT",
                 np.round(self.start_pos, 3), np.round(finish_xy, 3))

    def step(self, dt: float) -> str:
        """Один шаг контура управления. Возвращает текущую фазу."""
        if self.fsm is None:
            raise RuntimeError("Mission is not started, call start_mission() first")
        fsm = self.fsm
        self.step_count += 1

        # 1. Телеметрия груза (если пакет потерян — используем последнюю известную позицию)
        pos = self.read_payload_position()
        if pos is not None:
            self.payload_pos = pos
        payload_pos = self.payload_pos

        # 2. Переключение автомата состояний
        target_center_xy, current_cmd_z = fsm.update(payload_pos[2], dt, self.traj)
        target_drone_z = fsm.target_drone_z

        # 3. Anti-Sway работает только в полете по траектории
        sway_active = self.use_anti_sway and fsm.phase == SwarmFlightPhase.TRAJECTORY
        if sway_active and not self._sway_active:
            for ctrl in self.anti_sways.values():
                ctrl.reset()
        self._sway_active = sway_active

        # 4. Команды дронам и считывание телеметрии дронов
        now_ms = get_unix_time_milliseconds()
        drones_positions = {}
        for d_id in range(1, self.num_drones + 1):
            d_pos = self.read_drone_position(d_id)
            if d_pos is None:
                d_pos = payload_pos + self.offsets[d_id] + np.array([0.0, 0.0, self.hang_height])
            drones_positions[d_id] = d_pos

            if sway_active:
                sway_corr = self.anti_sways[d_id].compute_sway_correction(
                    d_pos, payload_pos, dt, nominal_offset=self.offsets[d_id])
            else:
                sway_corr = np.zeros(2)

            target_pos_py = np.array([
                target_center_xy[0] + self.offsets[d_id][0] + sway_corr[0],
                target_center_xy[1] + self.offsets[d_id][1] + sway_corr[1],
                target_drone_z,
            ])

            self.client.publish(drone_target_topic(d_id), Pose(
                position=py_to_unity_v3(target_pos_py),
                rotation=Quaternion.identity(),
                timestamp=now_ms,
            ))

        # 5. Сбор телеметрии натяжения тросов
        cables_forces = self.get_cables_forces()
        avg_tension = float(np.mean(list(cables_forces.values()))) if cables_forces else 0.0
        dist_to_finish = float(np.linalg.norm(payload_pos[:2] - fsm.finish_xy))

        # 6. Запись каждого шага в CSV
        if self.csv_logger is not None:
            self.csv_logger.log_step(
                timestamp_ms=now_ms,
                step=self.step_count,
                phase=fsm.phase,
                payload_pos=payload_pos,
                target_center_xy=target_center_xy,
                current_cmd_z=current_cmd_z,
                target_drone_z=target_drone_z,
                dist_to_finish=dist_to_finish,
                avg_tension=avg_tension,
                drones_positions=drones_positions,
                cables_forces=cables_forces,
            )

        # 7. Консольный лог
        every = self._param("CONSOLE_LOG_EVERY", 20)
        if every and self.step_count % every == 0:
            TelemetryLogger.log_status(self.step_count, fsm, payload_pos, avg_tension, self.start_pos)

        return fsm.phase

    def finish(self) -> None:
        if self.csv_logger is not None:
            self.csv_logger.close()
            self.csv_logger = None

    def run(self, realtime: bool = True, max_steps: int | None = None, stop_when_finished: bool = True,
            payload_timeout: float | None = None, before_step: Callable[[float], None] | None = None) -> str | None:
        """
        Полный цикл миссии. Возвращает конечную фазу (None, если груз не найден).

        realtime=True — шаг выдерживается по часам (DT), иначе шаги идут подряд
        с фиксированным dt (для ускоренной симуляции).
        before_step(dt) — вызывается перед каждым шагом (например, шаг физики симулятора).
        """
        payload_pos = self.wait_for_payload(timeout=payload_timeout)
        if payload_pos is None:
            log.error("Телеметрия груза не получена: проверьте, что сцена запущена и NetMQ сервер активен")
            return None

        self.start_mission(payload_pos)
        last_time = time.monotonic()

        try:
            while max_steps is None or self.step_count < max_steps:
                start_tick = time.monotonic()
                if realtime and self.step_count > 0:
                    current_dt = start_tick - last_time
                else:
                    current_dt = self.dt
                last_time = start_tick

                if before_step is not None:
                    before_step(current_dt)
                phase = self.step(current_dt)
                if stop_when_finished and phase == SwarmFlightPhase.FINISHED:
                    log.info("Миссия выполнена за %d шагов (%.1f с модельного времени)",
                             self.step_count, self.fsm.elapsed)
                    break

                # Синхронизация времени шага
                if realtime:
                    elapsed = time.monotonic() - start_tick
                    if elapsed < self.dt:
                        time.sleep(self.dt - elapsed)

        except KeyboardInterrupt:
            log.info("Остановка симуляции пользователем.")
        finally:
            self.finish()

        return self.fsm.phase
