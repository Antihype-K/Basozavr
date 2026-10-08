# control/flight_state_machine.py
import logging

import numpy as np

log = logging.getLogger("swarm.fsm")


class SwarmFlightPhase:
    LIFT = "LIFT"
    TRAJECTORY = "TRAJECTORY"
    HOVER = "HOVER"
    LAND = "LAND"
    LAND_DRONES = "LAND_DRONES"
    FINISHED = "FINISHED"

    # Фазы, в которых дроны держат груз на тросах на высоте cmd_z + hang_height
    CARRYING = (LIFT, TRAJECTORY, HOVER, LAND)


class FlightStateMachine:
    """
    Автомат состояний миссии: LIFT -> TRAJECTORY -> HOVER -> LAND -> LAND_DRONES -> FINISHED.

    Время отсчитывается по сумме переданных dt (а не по часам), поэтому автомат
    детерминирован и одинаково работает в реальном времени и в ускоренной симуляции.
    """

    def __init__(self, start_pos, finish_xy, target_flight_z: float = 3.0, target_land_z: float = 0.5,
                 climb_rate: float = 0.6, hang_height: float = 0.0, drone_land_z: float = 0.25,
                 hover_time: float = 2.0, lift_tolerance: float = 0.35, land_tolerance: float = 0.05,
                 land_settle_time: float = 3.0, finish_tolerance: float = 0.3):
        self.phase = SwarmFlightPhase.LIFT
        self.start_x, self.start_y = float(start_pos[0]), float(start_pos[1])
        self.finish_xy = np.asarray(finish_xy, dtype=float)

        self.target_flight_z = target_flight_z
        self.target_land_z = target_land_z
        self.climb_rate = climb_rate
        self.hang_height = hang_height
        self.drone_land_z = drone_land_z
        self.hover_time = hover_time
        self.lift_tolerance = lift_tolerance
        self.land_tolerance = land_tolerance
        self.land_settle_time = land_settle_time
        self.finish_tolerance = finish_tolerance

        self.current_cmd_z = float(start_pos[2])
        self.target_drone_z = self.current_cmd_z

        self.time_in_phase = 0.0
        self.hover_start_time: float | None = None  # совместимость: время входа в HOVER (с от старта)
        self.elapsed = 0.0

    @property
    def hover_remaining(self) -> float:
        if self.phase != SwarmFlightPhase.HOVER:
            return 0.0
        return max(0.0, self.hover_time - self.time_in_phase)

    @property
    def is_finished(self) -> bool:
        return self.phase == SwarmFlightPhase.FINISHED

    def _set_phase(self, phase: str, message: str) -> None:
        self.phase = phase
        self.time_in_phase = 0.0
        log.info(">>> [%s] %s", phase, message)

    def update(self, current_payload_z: float, current_dt: float, traj_generator):
        """Возвращает (target_center_xy, current_cmd_z) в зависимости от фазы."""
        dt = max(0.0, current_dt)
        self.elapsed += dt
        self.time_in_phase += dt
        target_center_xy = self.finish_xy

        if self.phase == SwarmFlightPhase.LIFT:
            self.current_cmd_z = min(self.target_flight_z, self.current_cmd_z + self.climb_rate * dt)
            target_center_xy = np.array([self.start_x, self.start_y])

            if current_payload_z >= self.target_flight_z - self.lift_tolerance:
                self._set_phase(SwarmFlightPhase.TRAJECTORY, "Подъем завершен, движение по траектории")

        elif self.phase == SwarmFlightPhase.TRAJECTORY:
            self.current_cmd_z = self.target_flight_z
            target_center_xy = np.asarray(traj_generator.update(dt), dtype=float)[:2]

            dist_cmd_to_finish = float(np.linalg.norm(target_center_xy - self.finish_xy))
            # Генератор с признаком завершения доводит уставку точно до цели;
            # допуск по расстоянию — только для генераторов без is_finished
            if hasattr(traj_generator, "is_finished"):
                arrived = traj_generator.is_finished
            else:
                arrived = dist_cmd_to_finish < self.finish_tolerance

            if arrived:
                self.hover_start_time = self.elapsed
                self._set_phase(SwarmFlightPhase.HOVER,
                                f"Уставка в {dist_cmd_to_finish:.2f} м от точки доставки, стабилизация")

        elif self.phase == SwarmFlightPhase.HOVER:
            self.current_cmd_z = self.target_flight_z

            if self.time_in_phase >= self.hover_time:
                self._set_phase(SwarmFlightPhase.LAND, "Стабилизация завершена, посадка груза")

        elif self.phase == SwarmFlightPhase.LAND:
            self.current_cmd_z = max(self.target_land_z, self.current_cmd_z - self.climb_rate * dt)

            payload_down = current_payload_z <= self.target_land_z + self.land_tolerance
            # Если груз высокий и не опускается до порога — ждем и все равно сажаем дроны
            cmd_down_for = self.time_in_phase - (self.target_flight_z - self.target_land_z) / self.climb_rate
            if payload_down or cmd_down_for >= self.land_settle_time:
                self._set_phase(SwarmFlightPhase.LAND_DRONES, "Груз на земле, посадка дронов")

        elif self.phase == SwarmFlightPhase.LAND_DRONES:
            self.target_drone_z = max(self.drone_land_z, self.target_drone_z - self.climb_rate * dt)
            if self.target_drone_z <= self.drone_land_z + 1e-9:
                self._set_phase(SwarmFlightPhase.FINISHED, "Посадка дронов завершена, миссия выполнена")

        if self.phase in SwarmFlightPhase.CARRYING:
            # Уставка дронов догоняет cmd_z + hang_height с ограниченной скоростью:
            # без этого на первом шаге дроны рывком натягивают тросы
            desired = self.current_cmd_z + self.hang_height
            max_step = 2.0 * self.climb_rate * dt
            self.target_drone_z += min(max(desired - self.target_drone_z, -max_step), max_step)
        elif self.phase == SwarmFlightPhase.FINISHED:
            self.target_drone_z = self.drone_land_z

        return target_center_xy, self.current_cmd_z
