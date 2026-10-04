import os
import csv
import time
import numpy as np
from control.flight_state_machine import SwarmFlightPhase


class CSVLogger:
    """Модуль сохранения полной полетной телеметрии в CSV-файл."""

    def __init__(self, filename=None, num_drones=6):
        self.num_drones = num_drones

        if filename is None:
            os.makedirs("logs", exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"logs/flight_log_{timestamp}.csv"

        self.filename = filename
        self.file = open(self.filename, mode="w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)

        # Формируем динамический заголовок CSV
        header = [
            "timestamp", "step", "phase",
            "payload_x", "payload_y", "payload_z",
            "target_cmd_x", "target_cmd_y", "target_cmd_z",
            "target_drone_z", "dist_to_finish", "avg_cable_tension"
        ]

        # Добавляем колонки для каждого дрона (координаты и натяжение его троса)
        for d_id in range(1, self.num_drones + 1):
            header.extend([
                f"drone_{d_id}_x", f"drone_{d_id}_y", f"drone_{d_id}_z",
                f"cable_force_{d_id}"
            ])

        self.writer.writerow(header)
        print(f"[CSVLogger] Логирование полёта запущено в файл: {self.filename}")

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
        cables_forces: dict
    ):
        """Запись телеметрии текущего физического шага."""
        row = [
            timestamp_ms, step, phase,
            f"{payload_pos[0]:.4f}", f"{payload_pos[1]:.4f}", f"{payload_pos[2]:.4f}",
            f"{target_center_xy[0]:.4f}", f"{target_center_xy[1]:.4f}", f"{current_cmd_z:.4f}",
            f"{target_drone_z:.4f}", f"{dist_to_finish:.4f}", f"{avg_tension:.4f}"
        ]

        # Дописываем позицию каждого дрона и силу натяжения его троса
        for d_id in range(1, self.num_drones + 1):
            d_pos = drones_positions.get(d_id, np.array([0.0, 0.0, 0.0]))
            d_force = cables_forces.get(d_id, 0.0)
            row.extend([
                f"{d_pos[0]:.4f}", f"{d_pos[1]:.4f}", f"{d_pos[2]:.4f}",
                f"{d_force:.4f}"
            ])

        self.writer.writerow(row)

    def close(self):
        """Безопасное закрытие файла."""
        if self.file and not self.file.closed:
            self.file.flush()
            self.file.close()
            print(f"[CSVLogger] Файл телеметрии сохранен: {self.filename}")


class TelemetryLogger:
    """Консольная контекстная телеметрия."""

    @staticmethod
    def log_status(step_count, phase, payload_pos, finish_xy, avg_tension, current_cmd_z, target_drone_z, start_pos, hover_start_time):
        current_xy = payload_pos[:2]
        dist_to_final_target = np.linalg.norm(current_xy - finish_xy)

        common_info = (
            f"[{step_count:06d}] [{phase:<11}] | "
            f"Груз Pos: [{payload_pos[0]:6.2f}, {payload_pos[1]:6.2f}, {payload_pos[2]:5.2f}m] | "
            f"До финиша: {dist_to_final_target:5.2f}m | "
            f"Натяжение avg: {avg_tension:5.1f}N"
        )

        phase_info = ""
        if phase == SwarmFlightPhase.LIFT:
            lift_progress = min(100.0, (payload_pos[2] / 3.0) * 100.0)
            phase_info = f" -> [ПОДЪЕМ] Прогресс: {lift_progress:5.1f}% | Уставка Z: {current_cmd_z:.2f}m"

        elif phase == SwarmFlightPhase.TRAJECTORY:
            traj_dist_total = np.linalg.norm(np.array([start_pos[0], start_pos[1]]) - finish_xy)
            traj_progress = min(100.0, ((traj_dist_total - dist_to_final_target) / traj_dist_total) * 100.0)
            phase_info = f" -> [ПОЛЕТ] Маршрут: {traj_progress:5.1f}% | AntiSway: Вкл"

        elif phase == SwarmFlightPhase.HOVER:
            remaining_hover = max(0.0, 2.0 - (time.time() - (hover_start_time or time.time())))
            phase_info = f" -> [СТАБИЛИЗАЦИЯ] Таймер HOVER: {remaining_hover:4.1f}s"

        elif phase == SwarmFlightPhase.LAND:
            land_progress = max(0.0, (1.0 - (payload_pos[2] - 0.5) / (3.0 - 0.5)) * 100.0)
            phase_info = f" -> [ПОСАДКА ГРУЗА] Прогресс: {land_progress:5.1f}% | Уставка Z: {current_cmd_z:.2f}m"

        elif phase == SwarmFlightPhase.LAND_DRONES:
            phase_info = f" -> [ПОСАДКА ДРОНОВ] Z дронов: {target_drone_z:.2f}m (Цель: 0.25m)"

        elif phase == SwarmFlightPhase.FINISHED:
            phase_info = " -> [ФИНИШ] Миссия успешно выполнена."

        print(common_info + phase_info)