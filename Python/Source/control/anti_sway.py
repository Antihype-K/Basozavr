# control/anti_sway.py
import numpy as np
import config as cfg

class AntiSwayController:
    def __init__(self, k_sway: float = 1.8, d_sway: float = 0.6):
        """
        k_sway: пропорциональный коэффициент коррекции по углу троса
        d_sway: дифференциальный коэффициент (по угловой скорости троса)
        """
        self.k_sway = k_sway
        self.d_sway = d_sway
        self.prev_angle_vector = np.zeros(2, dtype=float)

    def compute_sway_correction(self, drone_pos: np.ndarray, payload_pos: np.ndarray, dt: float) -> np.ndarray:
        """
        Возвращает векторы добавки к целевой позиции [dx, dy] для гашения раскачки.
        """
        delta = drone_pos - payload_pos
        length = np.linalg.norm(delta)
        
        if length < 1e-3:
            return np.zeros(2, dtype=float)

        # Проекция угла отклонения троса от вертикали по оси X и Y (в радианах)
        angle_x = np.arctan2(delta[0], delta[2])
        angle_y = np.arctan2(delta[1], delta[2])
        angle_vector = np.array([angle_x, angle_y])

        # Скорость изменения угла (угловая скорость маятника)
        angle_rate = (angle_vector - self.prev_angle_vector) / dt if dt > 0 else np.zeros(2)
        self.prev_angle_vector = angle_vector

        # Формула упреждающего смещения дрона в сторону раскачки
        correction_xy = -self.k_sway * angle_vector - self.d_sway * angle_rate
        return correction_xy