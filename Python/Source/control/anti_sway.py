# control/anti_sway.py
import numpy as np


class AntiSwayController:
    """
    PD-коррекция позиции дрона для гашения маятниковой раскачки груза.

    Раскачка считается относительно *номинальной* геометрии троса: в формации
    дрон смещен от центра груза на `nominal_offset` (радиус формации), и этот
    штатный наклон троса не должен вызывать коррекцию.
    """

    def __init__(self, k_sway: float = 1.8, d_sway: float = 0.6, max_correction: float | None = None):
        """
        k_sway: пропорциональный коэффициент коррекции по углу отклонения троса
        d_sway: дифференциальный коэффициент (по угловой скорости троса)
        max_correction: ограничение модуля коррекции (м), None — без ограничения
        """
        self.k_sway = k_sway
        self.d_sway = d_sway
        self.max_correction = max_correction
        self.prev_angle_vector: np.ndarray | None = None

    def reset(self) -> None:
        """Сбрасывает память производной (вызывать при включении контроллера)."""
        self.prev_angle_vector = None

    def compute_sway_correction(self, drone_pos: np.ndarray, payload_pos: np.ndarray, dt: float,
                                nominal_offset: np.ndarray | None = None) -> np.ndarray:
        """
        Возвращает добавку к целевой позиции дрона [dx, dy] для гашения раскачки.

        drone_pos, payload_pos: [x, y, z] в системе Python (Z — вверх)
        nominal_offset: штатное смещение дрона относительно центра груза [dx, dy(, dz)]
        """
        drone_pos = np.asarray(drone_pos, dtype=float)
        payload_pos = np.asarray(payload_pos, dtype=float)

        # Где груз должен висеть под этим дроном при отсутствии раскачки
        expected_payload_xy = drone_pos[:2]
        if nominal_offset is not None:
            expected_payload_xy = expected_payload_xy - np.asarray(nominal_offset, dtype=float)[:2]

        deviation_xy = payload_pos[:2] - expected_payload_xy
        height = drone_pos[2] - payload_pos[2]

        if height < 1e-3:
            # Груз на уровне дрона или выше — геометрия маятника не определена
            self.prev_angle_vector = None
            return np.zeros(2, dtype=float)

        # Углы отклонения груза от номинали по осям X и Y (рад)
        angle_vector = np.arctan2(deviation_xy, height)

        # Угловая скорость маятника (на первом шаге — 0, без скачка производной)
        if self.prev_angle_vector is None or dt <= 0:
            angle_rate = np.zeros(2, dtype=float)
        else:
            angle_rate = (angle_vector - self.prev_angle_vector) / dt
        self.prev_angle_vector = angle_vector

        # Дрон смещается в сторону отклонения груза, «подбегая» под маятник
        correction_xy = self.k_sway * angle_vector + self.d_sway * angle_rate

        if self.max_correction is not None:
            norm = float(np.linalg.norm(correction_xy))
            if norm > self.max_correction:
                correction_xy *= self.max_correction / norm

        return correction_xy
