# control/trajectory.py
import numpy as np

class JerkLimitedTrajectory:
    def __init__(self, start_pos: np.ndarray, target_pos: np.ndarray, 
                 v_max: float = 2.0, a_max: float = 1.0, j_max: float = 2.0):
        self.start_pos = np.array(start_pos, dtype=float)
        self.target_pos = np.array(target_pos, dtype=float)
        
        self.v_max = v_max
        self.a_max = a_max
        self.j_max = j_max
        
        self.curr_pos = np.copy(self.start_pos)
        self.curr_vel = np.zeros(3, dtype=float)
        self.curr_acc = np.zeros(3, dtype=float)

    def update(self, dt: float) -> np.ndarray:
        """ Генерирует плавно обновляемую текущую целевую точку на каждом шаге dt """
        direction = self.target_pos - self.curr_pos
        dist = np.linalg.norm(direction)
        
        if dist < 1e-3:
            return self.target_pos

        dir_unit = direction / dist
        
        # Простейшее профилирование скорости с торможением у цели
        target_v = min(self.v_max, np.sqrt(2 * self.a_max * dist))
        desired_vel = dir_unit * target_v
        
        # Ограничение ускорения и рывка
        acc_error = (desired_vel - self.curr_vel) / dt if dt > 0 else np.zeros(3)
        acc_error = np.clip(acc_error, -self.a_max, self.a_max)
        
        jerk = (acc_error - self.curr_acc) / dt if dt > 0 else np.zeros(3)
        jerk = np.clip(jerk, -self.j_max, self.j_max)
        
        self.curr_acc += jerk * dt
        self.curr_vel += self.curr_acc * dt
        self.curr_pos += self.curr_vel * dt
        
        return self.curr_pos