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
        self.initialized = False

    def compute_sway_correction(self, drone_pos: np.ndarray, payload_pos: np.ndarray, dt: float,
                                nominal_offset: np.ndarray = None) -> np.ndarray:
        """
        Возвращает векторы добавки к целевой позиции [dx, dy] для гашения раскачки.

        nominal_offset — номинальное смещение дрона от груза в строю ([dx, dy, 0], FormationManager).
        Раскачкой считается только отклонение от него: без этого угол троса включает радиус строя
        (~40° при R=1.414 и высоте 1.6 м), и поправка -K*угол сжимает строй к центру вместо гашения маятника.
        """
        delta = drone_pos - payload_pos
        if nominal_offset is not None:
            delta = delta - np.asarray(nominal_offset, dtype=float)
        length = np.linalg.norm(delta)
        
        if length < 1e-3:
            return np.zeros(2, dtype=float)

        # Проекция угла отклонения троса от вертикали по оси X и Y (в радианах)
        angle_x = np.arctan2(delta[0], delta[2])
        angle_y = np.arctan2(delta[1], delta[2])
        angle_vector = np.array([angle_x, angle_y])

        # Скорость изменения угла (угловая скорость маятника)
        # На первом вызове производной нет: иначе (угол - 0)/dt даёт выброс уставки на десятки метров
        if not self.initialized:
            self.prev_angle_vector = angle_vector
            self.initialized = True
        angle_rate = (angle_vector - self.prev_angle_vector) / dt if dt > 0 else np.zeros(2)
        self.prev_angle_vector = angle_vector

        # Формула упреждающего смещения дрона в сторону раскачки
        correction_xy = -self.k_sway * angle_vector - self.d_sway * angle_rate
        return correction_xy