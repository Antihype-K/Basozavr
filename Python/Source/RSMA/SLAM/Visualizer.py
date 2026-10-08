import math

import matplotlib.pyplot as plt
import numpy as np

from RSMA.SLAM.Config import Config


class SlamVisualizerMatplotlib:
    """Визуализация карты SLAM и положения робота."""
    def __init__(self, config: Config):
        self.map_size = config.map_size_pixels
        self.map_scale = config.map_size_pixels / (config.map_size_meters * 1000.0)
        self.center_offset_mm = (config.map_size_meters * 1000.0) / 2.0

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.ax.set_title("RSMA & BreezeSLAM Map")

        init_map = np.full((self.map_size, self.map_size), 127, dtype=np.uint8)
        self.im = self.ax.imshow(init_map, cmap='gray', vmin=0, vmax=255, origin='upper')

        self.robot_marker, = self.ax.plot([], [], 'go', markersize=12, label='Robot', zorder=5)
        self.direction_line, = self.ax.plot([], [], 'r-', linewidth=3, zorder=4)

        self.coord_text = self.ax.text(
            15, 35, "", color="cyan", fontsize=12,
            bbox=dict(facecolor='black', alpha=0.8)
        )

        self.ax.axis('off')
        self.is_open = True
        self.fig.canvas.mpl_connect('close_event', self._on_close)

    def _on_close(self, event):
        self.is_open = False

    def display(self, map_bytes, robot_x_mm, robot_y_mm, robot_theta_deg):
        if not self.is_open:
            return False

        map_img = np.frombuffer(map_bytes, dtype=np.uint8).reshape((self.map_size, self.map_size))

        # Пересчет в пиксели экрана
        relative_x_mm = robot_x_mm - self.center_offset_mm
        relative_y_mm = robot_y_mm - self.center_offset_mm

        # Ось X оставляем как есть (слева направо)
        pixel_x = (self.map_size // 2) + relative_x_mm * self.map_scale

        # Ось Y инвертируем! Т.к. в SLAM +Y — это вверх, а на экране +Y — это вниз.
        # Чтобы поехать вверх на экране, мы должны вычитать из центра
        pixel_y = (self.map_size // 2) - relative_y_mm * self.map_scale

        # Переводим угол в радианы
        angle_rad = math.radians(robot_theta_deg)
        arrow_len = 25

        # Для dir_x и dir_y знаки должны строго соответствовать логике осей pixel_x и pixel_y
        dir_x = pixel_x + arrow_len * math.cos(angle_rad)
        dir_y = pixel_y - arrow_len * math.sin(angle_rad) # Здесь минус верный, т.к. Y инвертирован выше

        self.im.set_data(map_img)

        status_info = (
            f"SLAM Robot Pos:\n"
            f"X: {robot_x_mm/1000.0:.2f} m (Px: {int(pixel_x)})\n"
            f"Y: {robot_y_mm/1000.0:.2f} m (Px: {int(pixel_y)})\n"
            f"Angle: {robot_theta_deg:.1f}°"
        )
        self.coord_text.set_text(status_info)

        if 0 <= pixel_x < self.map_size and 0 <= pixel_y < self.map_size:
            self.robot_marker.set_data([pixel_x], [pixel_y])
            self.direction_line.set_data([pixel_x, dir_x], [pixel_y, dir_y])
            self.coord_text.set_color("lime")
        else:
            edge_x = max(10, min(self.map_size - 10, pixel_x))
            edge_y = max(10, min(self.map_size - 10, pixel_y))
            self.robot_marker.set_data([edge_x], [edge_y])
            self.direction_line.set_data([], [])
            self.coord_text.set_color("red")

        self.fig.canvas.flush_events()
        return True

    def close(self):
        plt.ioff()
        plt.close('all')
