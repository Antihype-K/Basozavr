import time
import numpy as np

class SwarmFlightPhase:
    LIFT = "LIFT"
    TRAJECTORY = "TRAJECTORY"
    HOVER = "HOVER"
    LAND = "LAND"
    LAND_DRONES = "LAND_DRONES"
    FINISHED = "FINISHED"

class FlightStateMachine:
    def __init__(self, start_pos, finish_xy, target_flight_z=3.0, target_land_z=None, climb_rate=0.6):
        self.phase = SwarmFlightPhase.LIFT
        self.start_x, self.start_y = start_pos[0], start_pos[1]
        self.finish_xy = finish_xy
        
        self.target_flight_z = target_flight_z
        # Уставка посадки по умолчанию — высота земли (стартовая высота груза). Груз висит на ~0,2 м выше уставки
        # (запас натяжения в высоте дронов), поэтому касание считаем с допуском 0,35 м от стартовой высоты.
        self.target_land_z = start_pos[2] if target_land_z is None else target_land_z
        self.land_done_z = start_pos[2] + 0.35
        self.climb_rate = climb_rate
        
        self.current_cmd_z = start_pos[2]
        self.hover_start_time = None

    def update(self, current_payload_z, current_dt, traj_generator):
        """Возвращает (target_center_xy, current_cmd_z) в зависимости от фазы"""
        
        if self.phase == SwarmFlightPhase.LIFT:
            self.current_cmd_z = min(self.target_flight_z, self.current_cmd_z + self.climb_rate * current_dt)
            target_center_xy = np.array([self.start_x, self.start_y])

            if current_payload_z >= 2.65:
                self.phase = SwarmFlightPhase.TRAJECTORY
                print("\n" + "="*70 + "\n>>> [ПОДЪЕМ ЗАВЕРШЕН] Переход к движению по траектории! <<<\n" + "="*70 + "\n")

        elif self.phase == SwarmFlightPhase.TRAJECTORY:
            self.current_cmd_z = self.target_flight_z
            traj_target = traj_generator.update(current_dt)
            target_center_xy = traj_target[:2]

            dist_cmd_to_finish = np.linalg.norm(target_center_xy - self.finish_xy)
            traj_done = getattr(traj_generator, 'is_finished', False) or getattr(traj_generator, 'finished', False)

            if dist_cmd_to_finish < 0.3 or traj_done:
                self.phase = SwarmFlightPhase.HOVER
                self.hover_start_time = time.time()
                print("\n" + "="*70 + f"\n>>> [ТОЧКА ДОСТИГНУТА] Уставка подошла на {dist_cmd_to_finish:.2f}m. Включение HOVER... <<<\n" + "="*70 + "\n")

        elif self.phase == SwarmFlightPhase.HOVER:
            self.current_cmd_z = self.target_flight_z
            target_center_xy = self.finish_xy

            if time.time() - self.hover_start_time > 2.0:
                self.phase = SwarmFlightPhase.LAND
                print("\n" + "="*70 + "\n>>> [СТАБИЛИЗАЦИЯ ЗАВЕРШЕНА] Начало посадки груза! <<<\n" + "="*70 + "\n")

        elif self.phase == SwarmFlightPhase.LAND:
            self.current_cmd_z = max(self.target_land_z, self.current_cmd_z - self.climb_rate * current_dt)
            target_center_xy = self.finish_xy

            if current_payload_z <= self.land_done_z:
                self.phase = SwarmFlightPhase.LAND_DRONES
                print("\n" + "="*70 + "\n>>> [ГРУЗ НА ЗЕМЛЕ] Начинаем посадку самих дронов... <<<\n" + "="*70 + "\n")

        elif self.phase == SwarmFlightPhase.LAND_DRONES:
            target_center_xy = self.finish_xy

        elif self.phase == SwarmFlightPhase.FINISHED:
            target_center_xy = self.finish_xy

        return target_center_xy, self.current_cmd_z