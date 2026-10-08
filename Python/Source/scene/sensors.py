import numpy as np

from RSMA.uDTP.Topics import CameraFramePacket


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
