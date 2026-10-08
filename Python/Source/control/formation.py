# control/formation.py
import numpy as np


class FormationManager:
    def __init__(self, num_drones: int, radius: float = 1.414):
        self.num_drones = num_drones
        self.radius = radius

    def get_formation_offsets(self) -> dict[int, np.ndarray]:
        """
        Генерирует относительные смещения [dx, dy, dz] для дронов в формате
        правильного N-угольника относительно центра массы роя.
        """
        offsets = {}
        angles = np.linspace(0, 2 * np.pi, self.num_drones, endpoint=False)

        # Сдвиг угла для правильной ориентации (например, квадрат 2x2 м)
        angle_offset = np.pi / 4 if self.num_drones == 4 else 0.0

        for idx, angle in enumerate(angles, start=1):
            a = angle + angle_offset
            dx = self.radius * np.cos(a)
            dy = self.radius * np.sin(a)
            offsets[idx] = np.array([dx, dy, 0.0])

        return offsets
