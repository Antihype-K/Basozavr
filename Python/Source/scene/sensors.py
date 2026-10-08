import math

import numpy as np

from RSMA.uDTP.Topics import CameraFramePacket, Float32, LaserScan128, LaserScan256


class Lidar:
    """
    Лидар Lidar.cs. Луч i направлен под углом angleMin + i * angleIncrement (градусы)
    вокруг оси Y датчика, 0° — вперед (+Z датчика), углы растут по часовой стрелке.

        lidar = sim.lidar("Lidar")
        print(lidar.min_distance())
        xz = lidar.points()           # точки в системе датчика: [x (вправо), z (вперед)]
    """

    def __init__(self, sim, topic: str = "Lidar", size: int = 128):
        if size not in (128, 256):
            raise ValueError("size must be 128 or 256 (LaserScan128 / LaserScan256)")
        self.sim = sim
        self.topic = topic
        self.msg_type = LaserScan128 if size == 128 else LaserScan256

    def scan(self):
        """Последний скан (LaserScan128/256) или None."""
        return self.sim.get(self.topic, self.msg_type)

    def ranges(self) -> np.ndarray:
        scan = self.scan()
        return np.array([] if scan is None else scan.ranges, dtype=float)

    def angles(self) -> np.ndarray:
        """Углы лучей в градусах."""
        scan = self.scan()
        if scan is None:
            return np.array([], dtype=float)
        return scan.angleMin + np.arange(len(scan.ranges)) * scan.angleIncrement

    def points(self, only_hits: bool = True) -> np.ndarray:
        """Точки отражений в системе датчика, массив N x 2: (x, z)."""
        scan = self.scan()
        if scan is None or not scan.ranges:
            return np.zeros((0, 2))
        r = np.array(scan.ranges, dtype=float)
        a = np.radians(scan.angleMin + np.arange(len(r)) * scan.angleIncrement)
        pts = np.column_stack([r * np.sin(a), r * np.cos(a)])
        if only_hits:
            pts = pts[r < scan.rangeMax - 1e-6]
        return pts

    def min_distance(self) -> float | None:
        r = self.ranges()
        return float(r.min()) if r.size else None

    def distance_at(self, angle: float) -> float | None:
        """Дальность луча, ближайшего к углу angle (градусы)."""
        scan = self.scan()
        if scan is None or not scan.ranges:
            return None
        angles = scan.angleMin + np.arange(len(scan.ranges)) * scan.angleIncrement
        diff = np.abs((angles - angle + 180.0) % 360.0 - 180.0)
        return float(scan.ranges[int(np.argmin(diff))])


class RangeFinder:
    """Дальномер RangeFinder.cs (топик Float32)."""

    def __init__(self, sim, topic: str = "RangeFinder"):
        self.sim = sim
        self.topic = topic

    def distance(self) -> float | None:
        msg = self.sim.get(self.topic, Float32)
        return None if msg is None else float(msg.value)


class Camera:
    """
    Камера RSMACamera.cs (топик Camera_<id>, кадры RGB24).

        frame = sim.camera(0).frame()     # numpy-массив H x W x 3, uint8
    """

    def __init__(self, sim, camera_id: int = 0):
        self.sim = sim
        self.topic = f"Camera_{camera_id}"

    def packet(self) -> CameraFramePacket | None:
        return self.sim.get(self.topic, CameraFramePacket)

    def frame(self, flip: bool = True) -> np.ndarray | None:
        """
        Последний кадр H x W x 3 (RGB) или None.
        flip=True переворачивает строки: AsyncGPUReadback отдает изображение снизу вверх.
        """
        pkt = self.packet()
        if pkt is None or not pkt.pixelData:
            return None
        channels = pkt.channels or 3
        expected = pkt.width * pkt.height * channels
        data = np.frombuffer(pkt.pixelData, dtype=np.uint8)
        if data.size != expected:
            raise ValueError(f"Кадр {self.topic}: {data.size} байт вместо {expected}")
        img = data.reshape(pkt.height, pkt.width, channels)
        return img[::-1] if flip else img

    def save(self, path: str, flip: bool = True) -> bool:
        """Сохраняет кадр в файл (png/jpg) через matplotlib."""
        img = self.frame(flip=flip)
        if img is None:
            return False
        import matplotlib.pyplot as plt

        plt.imsave(path, img)
        return True


def heading_vector(heading_deg: float) -> tuple[float, float]:
    """Единичный вектор (x, z) направления с рысканием heading_deg (градусы, как в Unity)."""
    rad = math.radians(heading_deg)
    return math.sin(rad), math.cos(rad)
