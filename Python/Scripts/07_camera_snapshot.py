"""
Сохраняет кадр с камеры RSMACamera (топик Camera_<id>) в PNG.

    python 07_camera_snapshot.py [--camera 0] [--out frame.png]
"""

import argparse

import _rsma_path  # noqa: F401

from scene import connect

parser = argparse.ArgumentParser()
parser.add_argument("--camera", type=int, default=0)
parser.add_argument("--out", default="frame.png")
args, _ = parser.parse_known_args()

with connect(description=__doc__) as sim:
    camera = sim.camera(args.camera)
    if not sim.wait_until(lambda: camera.packet() is not None, timeout=5):
        raise SystemExit(f"Нет кадров в топике Camera_{args.camera}: включен ли стриминг у RSMACamera?")
    frame = camera.frame()
    camera.save(args.out)
    print(f"Кадр {frame.shape[1]}x{frame.shape[0]} сохранен в {args.out}")
