import csv
import logging
import os
import time

import numpy as np

from control.flight_state_machine import SwarmFlightPhase

log = logging.getLogger("swarm.logger")


class CSVLogger:
    """Модуль сохранения полной полетной телеметрии в CSV-файл."""

    def __init__(self, filename: str | None = None, num_drones: int = 6, log_dir: str = "logs"):
        self.num_drones = num_drones

        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(log_dir, f"flight_log_{timestamp}.csv")
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

        self.filename = filename
        self.file = open(self.filename, mode="w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)

        # Формируем динамический заголовок CSV
        header = [
            "timestamp", "step", "phase",
            "payload_x", "payload_y", "payload_z",
            "target_cmd_x", "target_cmd_y", "target_cmd_z",
            "target_drone_z", "dist_to_finish", "avg_cable_tension",
        ]

        # Добавляем колонки для каждого дрона (координаты и натяжение его троса)
        for d_id in range(1, self.num_drones + 1):
            header.extend([
                f"drone_{d_id}_x", f"drone_{d_id}_y", f"drone_{d_id}_z",
                f"cable_force_{d_id}",
            ])

        self.writer.writerow(header)
        log.info("Логирование полёта запущено в файл: %s", self.filename)

    def log_step(
        self,
        timestamp_ms: int,
        step: int,
        phase: str,
        payload_pos: np.ndarray,
        target_center_xy: np.ndarray,
        current_cmd_z: float,
        target_drone_z: float,
        dist_to_finish: float,
        avg_tension: float,
        drones_positions: dict,
        cables_forces: dict,
    ):
        """Запись телеметрии текущего физического шага."""
        row = [
            timestamp_ms, step, phase,
            f"{payload_pos[0]:.4f}", f"{payload_pos[1]:.4f}", f"{payload_pos[2]:.4f}",
            f"{target_center_xy[0]:.4f}", f"{target_center_xy[1]:.4f}", f"{current_cmd_z:.4f}",
            f"{target_drone_z:.4f}", f"{dist_to_finish:.4f}", f"{avg_tension:.4f}",
        ]

        # Дописываем позицию каждого дрона и силу натяжения его троса
        for d_id in range(1, self.num_drones + 1):
            d_pos = drones_positions.get(d_id, np.zeros(3))
            d_force = cables_forces.get(d_id, 0.0)
            row.extend([
                f"{d_pos[0]:.4f}", f"{d_pos[1]:.4f}", f"{d_pos[2]:.4f}",
                f"{d_force:.4f}",
            ])

        self.writer.writerow(row)

    def close(self):
        """Безопасное закрытие файла."""
        if self.file and not self.file.closed:
            self.file.flush()
            self.file.close()
            log.info("Файл телеметрии сохранен: %s", self.filename)

    def __enter__(self) -> "CSVLogger":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class TelemetryLogger:
    """Консольная контекстная телеметрия."""

    @staticmethod
    def format_status(step_count, fsm, payload_pos, avg_tension, start_pos) -> str:
        phase = fsm.phase
        finish_xy = fsm.finish_xy
        dist_to_final_target = float(np.linalg.norm(np.asarray(payload_pos[:2]) - finish_xy))

        common_info = (
            f"[{step_count:06d}] [{phase:<11}] | "
            f"Груз Pos: [{payload_pos[0]:6.2f}, {payload_pos[1]:6.2f}, {payload_pos[2]:5.2f}m] | "
            f"До финиша: {dist_to_final_target:5.2f}m | "
            f"Натяжение avg: {avg_tension:5.1f}N"
        )

        phase_info = ""
        if phase == SwarmFlightPhase.LIFT:
            lift_range = fsm.target_flight_z - start_pos[2]
            lift_progress = 100.0 if lift_range <= 0 else (payload_pos[2] - start_pos[2]) / lift_range * 100.0
            lift_progress = min(100.0, max(0.0, lift_progress))
            phase_info = f" -> [ПОДЪЕМ] Прогресс: {lift_progress:5.1f}% | Уставка Z: {fsm.current_cmd_z:.2f}m"

        elif phase == SwarmFlightPhase.TRAJECTORY:
            traj_dist_total = float(np.linalg.norm(np.asarray(start_pos[:2]) - finish_xy))
            if traj_dist_total > 1e-6:
                traj_progress = min(100.0, max(0.0, (traj_dist_total - dist_to_final_target) / traj_dist_total * 100.0))
            else:
                traj_progress = 100.0
            phase_info = f" -> [ПОЛЕТ] Маршрут: {traj_progress:5.1f}%"

        elif phase == SwarmFlightPhase.HOVER:
            phase_info = f" -> [СТАБИЛИЗАЦИЯ] Таймер HOVER: {fsm.hover_remaining:4.1f}s"

        elif phase == SwarmFlightPhase.LAND:
            land_range = fsm.target_flight_z - fsm.target_land_z
            land_progress = 100.0 if land_range <= 0 else (fsm.target_flight_z - payload_pos[2]) / land_range * 100.0
            land_progress = min(100.0, max(0.0, land_progress))
            phase_info = f" -> [ПОСАДКА ГРУЗА] Прогресс: {land_progress:5.1f}% | Уставка Z: {fsm.current_cmd_z:.2f}m"

        elif phase == SwarmFlightPhase.LAND_DRONES:
            phase_info = f" -> [ПОСАДКА ДРОНОВ] Z дронов: {fsm.target_drone_z:.2f}m (Цель: {fsm.drone_land_z:.2f}m)"

        elif phase == SwarmFlightPhase.FINISHED:
            phase_info = " -> [ФИНИШ] Миссия успешно выполнена."

        return common_info + phase_info

    @classmethod
    def log_status(cls, step_count, fsm, payload_pos, avg_tension, start_pos) -> None:
        log.info(cls.format_status(step_count, fsm, payload_pos, avg_tension, start_pos))
