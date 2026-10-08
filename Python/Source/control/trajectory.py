# control/trajectory.py
import math

import numpy as np


class JerkLimitedTrajectory:
    """
    Straight-line rest-to-rest motion with an S-curve (7-segment) velocity profile.

    The profile is planned once from the limits, so on every step
    |velocity| <= v_max, |acceleration| <= a_max, |jerk| <= j_max hold exactly,
    there is no overshoot and the motion ends exactly at the target.
    For short paths the peak velocity/acceleration are reduced automatically.
    """

    def __init__(self, start_pos, target_pos,
                 v_max: float = 2.0, a_max: float = 1.0, j_max: float = 2.0):
        if v_max <= 0 or a_max <= 0 or j_max <= 0:
            raise ValueError("v_max, a_max and j_max must be positive")

        self.start_pos = np.array(start_pos, dtype=float)
        self.target_pos = np.array(target_pos, dtype=float)

        self.v_max = v_max
        self.a_max = a_max
        self.j_max = j_max

        path = self.target_pos - self.start_pos
        self.length = float(np.linalg.norm(path))
        self.direction = path / self.length if self.length > 0 else np.zeros_like(path)

        self._segments = self._plan()  # list of (duration, jerk)
        self.duration = sum(d for d, _ in self._segments)

        self.t = 0.0
        self.s = 0.0
        self.v = 0.0
        self.a = 0.0
        self.is_finished = self.length == 0.0

    # --- Планирование ---

    def _accel_time(self, v: float) -> tuple[float, float]:
        """Durations (jerk phase Tj, constant-acceleration phase Tc) to go 0 -> v."""
        a, j = self.a_max, self.j_max
        if v * j < a * a:  # a_max is never reached
            return math.sqrt(v / j), 0.0
        return a / j, v / a - a / j

    def _plan(self) -> list[tuple[float, float]]:
        if self.length == 0.0:
            return []

        def accel_distance(v: float) -> float:
            tj, tc = self._accel_time(v)
            return v * (2 * tj + tc) / 2.0  # symmetric profile: mean speed v/2

        v_peak = self.v_max
        if 2 * accel_distance(v_peak) > self.length:
            lo, hi = 0.0, v_peak
            for _ in range(100):
                mid = (lo + hi) / 2.0
                if 2 * accel_distance(mid) > self.length:
                    hi = mid
                else:
                    lo = mid
            v_peak = lo

        tj, tc = self._accel_time(v_peak)
        tv = max(0.0, (self.length - 2 * accel_distance(v_peak)) / v_peak) if v_peak > 0 else 0.0
        j = self.j_max
        return [(tj, j), (tc, 0.0), (tj, -j), (tv, 0.0), (tj, -j), (tc, 0.0), (tj, j)]

    def _state_at(self, t: float) -> tuple[float, float, float]:
        s = v = a = 0.0
        for duration, jerk in self._segments:
            if t <= 0:
                break
            dt = min(duration, t)
            s += v * dt + a * dt**2 / 2.0 + jerk * dt**3 / 6.0
            v += a * dt + jerk * dt**2 / 2.0
            a += jerk * dt
            t -= dt
        return s, v, a

    # --- Состояние ---

    @property
    def curr_pos(self) -> np.ndarray:
        return self.start_pos + self.direction * self.s

    @property
    def curr_vel(self) -> np.ndarray:
        return self.direction * self.v

    @property
    def curr_acc(self) -> np.ndarray:
        return self.direction * self.a

    @property
    def remaining(self) -> float:
        return self.length - self.s

    def update(self, dt: float) -> np.ndarray:
        """Advances the profile by dt and returns the current set point [x, y, z]."""
        if self.is_finished:
            return self.target_pos.copy()

        self.t += max(0.0, dt)
        if self.t >= self.duration:
            self.t = self.duration
            self.s, self.v, self.a = self.length, 0.0, 0.0
            self.is_finished = True
            return self.target_pos.copy()

        s, v, a = self._state_at(self.t)
        self.s = min(max(s, 0.0), self.length)
        self.v, self.a = v, a
        return self.curr_pos
