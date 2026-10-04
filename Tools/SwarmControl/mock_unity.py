"""
Упрощённый имитатор Unity для проверки логики mission.py без редактора (ТОЛЬКО кинематика, не физика!).

Дроны отрабатывают цели с запаздыванием первого порядка, груз висит под центром строя, натяжение троса
считается из веса груза и угла троса. Протокол и топики те же, что у NetMQServer (RouterSocket).
Точность и динамику по нему не оценивать: для этого есть Tools/SwarmModel и сама Unity.

    python mock_unity.py --drones 6 --payload-mass 19.8 --port 5555
"""
import argparse
import json
import math
import threading
import time

import zmq

G = 9.81


class World:
    def __init__(self, n, mass, radius=3.0, cable=5.0, drone_h=1.0, tau=0.5):
        self.n, self.mass, self.cable, self.tau = n, mass, cable, tau
        self.start = (115.0, 0.2, 95.5)
        ang = [i * 2 * math.pi / n for i in range(n)]
        self.pos = [[self.start[0] + radius * math.cos(a), drone_h, self.start[2] + radius * math.sin(a)] for a in ang]
        self.target = [None] * n
        self.released = [False] * n
        self.radius = radius
        self.payload = list(self.start)
        self.lock = threading.Lock()
        self.hang = math.sqrt(cable ** 2 - radius ** 2)  # вертикальный размах троса под нагрузкой

    def step(self, dt):
        with self.lock:
            for i in range(self.n):
                if self.target[i]:
                    for k in range(3):
                        self.pos[i][k] += (self.target[i][k] - self.pos[i][k]) * min(1.0, dt / self.tau)
            cx = sum(p[0] for p in self.pos) / self.n
            cy = sum(p[1] for p in self.pos) / self.n
            cz = sum(p[2] for p in self.pos) / self.n
            if not all(self.released):
                self.payload = [cx, max(self.start[1], cy - self.hang), cz]

    def tension(self, i):
        if self.released[i]:
            return 0.0
        cy = sum(p[1] for p in self.pos) / self.n
        slack = max(0.0, min(1.0, (cy - self.start[1] - (self.hang - 1.5)) / 1.5))
        return self.mass * G / self.n / (self.hang / self.cable) * slack


def serve(world, port):
    sock = zmq.Context().socket(zmq.ROUTER)
    sock.bind(f"tcp://*:{port}")
    pose = lambda p: {"timestamp": 0, "position": {"x": p[0], "y": p[1], "z": p[2]}, "rotation": {"x": 0, "y": 0, "z": 0, "w": 1}}
    while True:
        ident, _, data = sock.recv_multipart()
        text = data.decode()
        if text == "GetServerStatus":
            reply = "OK: Server is running"
        else:
            p = json.loads(text)
            name = p["TopicName"]
            idx = int(name.rsplit("_", 1)[1]) - 1 if "_" in name else -1
            with world.lock:
                if p["Action"] == "publish":
                    d = json.loads(p["Data"])
                    if name.startswith("DroneTargetPose"):
                        world.target[idx] = [d["position"]["x"], d["position"]["y"], d["position"]["z"]]
                    elif name.startswith("CableRelease") and d["value"] > 0.5:
                        world.released[idx] = True
                    reply = json.dumps({"status": "ok"})
                else:
                    if name.startswith("DronePose"):
                        inner = pose(world.pos[idx])
                    elif name == "PayloadPose":
                        inner = pose(world.payload)
                    elif name.startswith("CableForce"):
                        inner = {"value": world.tension(idx), "timestamp": 0}
                    else:
                        inner = pose((0, 0, 0))
                    reply = json.dumps({"status": "ok", "data": json.dumps(inner)})
        sock.send_multipart([ident, b"", reply.encode()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--drones", type=int, default=6)
    ap.add_argument("--payload-mass", type=float, default=12.0)
    args = ap.parse_args()
    world = World(args.drones, args.payload_mass)
    threading.Thread(target=serve, args=(world, args.port), daemon=True).start()
    print(f"mock_unity на порту {args.port}: {args.drones} дронов, груз {args.payload_mass} кг (Ctrl+C — выход)")
    while True:
        world.step(0.01)
        time.sleep(0.01)


if __name__ == "__main__":
    main()
