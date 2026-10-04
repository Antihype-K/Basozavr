# control/swarm_controller.py

import time
import math
import numpy as np

import config as cfg
from RSMA.Client import RSMAClient
from RSMA.uDTP.Topics.Pose import Pose
from RSMA.Types.Quaternion import Quaternion
from RSMA.uDTP.Topics.Float32 import Float32
from RSMA.Time import get_unix_time_milliseconds

from control.formation import FormationManager
from control.trajectory import JerkLimitedTrajectory
from control.anti_sway import AntiSwayController
from control.flight_state_machine import FlightStateMachine, SwarmFlightPhase
from utils.rsma_helpers import py_to_unity_v3, unity_to_py_v3
from utils.logger import TelemetryLogger, CSVLogger


class SwarmRSMAController:
    def __init__(self):
        self.num_drones: int = getattr(cfg, 'NUM_DRONES', 6)
        self.formation_radius: float = getattr(cfg, 'FORMATION_RADIUS', 1.414)
        self.cable_length: float = getattr(cfg, 'CABLE_LENGTH', 2.0)
        self.dt = getattr(cfg, 'DT', 0.01)

        self.formation = FormationManager(num_drones=self.num_drones, radius=self.formation_radius)
        self.offsets = self.formation.get_formation_offsets()

        k_sway = getattr(cfg, 'K_SWAY', 0.15)
        d_sway = getattr(cfg, 'D_SWAY', 0.05)
        self.anti_sways = {
            d_id: AntiSwayController(k_sway=k_sway, d_sway=d_sway) 
            for d_id in range(1, self.num_drones + 1)
        }

        print("[Python API] Инициализация подключения к RSMA Broker...")
        self.client = RSMAClient()
        time.sleep(0.5)

    def get_cables_forces(self) -> dict:
        """Считывает силы натяжения каждого троса."""
        forces = {}
        for d_id in range(1, self.num_drones + 1):
            force_msg: Float32 = self.client.get_state(f"CableForce_{d_id}", Float32)
            if force_msg and hasattr(force_msg, 'value'):
                forces[d_id] = float(force_msg.value)
            elif force_msg is not None and isinstance(force_msg, (float, int)):
                forces[d_id] = float(force_msg)
            else:
                forces[d_id] = 0.0
        return forces

    def run(self):
        print("[Python API] Ожидание первой телеметрии груза из Unity...")
        
        payload_pos = None
        while payload_pos is None:
            payload_pose: Pose = self.client.get_state("PayloadPose", Pose)
            if payload_pose and payload_pose.position is not None:
                payload_pos = unity_to_py_v3(payload_pose.position)
            time.sleep(0.02)

        start_pos = payload_pos.copy()
        delta_x = getattr(cfg, 'TARGET_OFFSET_X', 15)
        delta_y = getattr(cfg, 'TARGET_OFFSET_Y', 8)
        finish_xy = np.array([start_pos[0] + delta_x, start_pos[1] + delta_y])
        flight_z = getattr(cfg, 'CRUISE_ALTITUDE', 3.0)

        # Подсистемы
        fsm = FlightStateMachine(start_pos=start_pos, finish_xy=finish_xy, target_flight_z=flight_z)
        traj = JerkLimitedTrajectory(
            start_pos=[start_pos[0], start_pos[1], 3.0], 
            target_pos=[finish_xy[0], finish_xy[1], 3.0], 
            v_max=getattr(cfg, 'V_MAX', 0.8)
        )
        csv_logger = CSVLogger(num_drones=self.num_drones)

        vertical_cable_len = math.sqrt(max(0.1, self.cable_length**2 - self.formation_radius**2))
        target_drone_z = start_pos[2] + vertical_cable_len + 0.2

        step_count = 0
        finished_steps = 0
        last_time = time.time()

        print(f"[Python API] Старт миссии! Исходная позиция: {payload_pos}. Фаза: LIFT")

        try:
            while True:
                start_tick = time.time()
                current_dt = start_tick - last_time if step_count > 0 else self.dt
                last_time = start_tick
                step_count += 1

                # 1. Телеметрия груза
                payload_pose: Pose = self.client.get_state("PayloadPose", Pose)
                if payload_pose and payload_pose.position is not None:
                    payload_pos = unity_to_py_v3(payload_pose.position)

                # 2. Переключение автомата состояний
                target_center_xy, current_cmd_z = fsm.update(payload_pos[2], current_dt, traj)

                # 3. Высота дронов
                if fsm.phase in [SwarmFlightPhase.LIFT, SwarmFlightPhase.TRAJECTORY, SwarmFlightPhase.HOVER, SwarmFlightPhase.LAND]:
                    target_drone_z = current_cmd_z + vertical_cable_len + 0.2
                elif fsm.phase == SwarmFlightPhase.LAND_DRONES:
                    target_drone_z = max(0.25, target_drone_z - fsm.climb_rate * current_dt)
                    if target_drone_z <= 0.28:
                        fsm.phase = SwarmFlightPhase.FINISHED
                        print("\n" + "="*70 + "\n>>> [ПОСАДКА ДРОНОВ ЗАВЕРШЕНА] Миссия выполнена! <<<\n" + "="*70 + "\n")
                elif fsm.phase == SwarmFlightPhase.FINISHED:
                    target_drone_z = 0.20

                # 4. Команды дронам и считывание телеметрии дронов
                now_ms = get_unix_time_milliseconds()
                payload_is_airborne = payload_pos[2] > 0.8
                
                drones_positions = {}
                for d_id in range(1, self.num_drones + 1):
                    d_pose = self.client.get_state(f"DronePose_{d_id}", Pose)
                    d_pos = unity_to_py_v3(d_pose.position) if (d_pose and d_pose.position) else payload_pos
                    drones_positions[d_id] = d_pos

                    if payload_is_airborne and fsm.phase == SwarmFlightPhase.TRAJECTORY:
                        sway_corr = self.anti_sways[d_id].compute_sway_correction(d_pos, payload_pos, current_dt, self.offsets[d_id])
                    else:
                        sway_corr = np.array([0.0, 0.0])

                    target_pos_py = np.array([
                        target_center_xy[0] + self.offsets[d_id][0] + sway_corr[0],
                        target_center_xy[1] + self.offsets[d_id][1] + sway_corr[1],
                        target_drone_z
                    ])

                    target_pose_msg = Pose(
                        position=py_to_unity_v3(target_pos_py),
                        rotation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
                        timestamp=now_ms
                    )
                    self.client.publish(f"DroneTargetPose_{d_id}", target_pose_msg)

                # 5. Сбор телеметрии натяжения тросов
                cables_forces = self.get_cables_forces()
                avg_tension = np.mean(list(cables_forces.values())) if cables_forces else 0.0
                dist_to_finish = np.linalg.norm(payload_pos[:2] - finish_xy)

                # 6. Запись каждого шага в CSV
                csv_logger.log_step(
                    timestamp_ms=now_ms,
                    step=step_count,
                    phase=fsm.phase,
                    payload_pos=payload_pos,
                    target_center_xy=target_center_xy,
                    current_cmd_z=current_cmd_z,
                    target_drone_z=target_drone_z,
                    dist_to_finish=dist_to_finish,
                    avg_tension=avg_tension,
                    drones_positions=drones_positions,
                    cables_forces=cables_forces
                )

                # 7. Консольный лог (каждые 20 шагов)
                if step_count % 20 == 0:
                    TelemetryLogger.log_status(
                        step_count, fsm.phase, payload_pos, finish_xy, 
                        avg_tension, current_cmd_z, target_drone_z, start_pos, fsm.hover_start_time
                    )

                # Миссия завершена: даём дронам постоять 100 шагов и выходим, чтобы сохранить CSV
                if fsm.phase == SwarmFlightPhase.FINISHED:
                    finished_steps += 1
                    if finished_steps > 100:
                        break

                # 8. Синхронизация времени шага
                elapsed = time.time() - start_tick
                if elapsed < self.dt:
                    time.sleep(self.dt - elapsed)

        except KeyboardInterrupt:
            print("\n[Python API] Остановка симуляции пользователем.")
        finally:
            csv_logger.close()