"""
Проверка связи Python <-> Unity (NetMQServer) и съём телеметрии роя.

Скрипт подключается к NetMQServer (RouterSocket, порт 5555 по умолчанию),
читает топики, которые публикуют Quadrocopter и RSMACable:
    DronePose_<id>        (Pose)    - фактическая позиция дрона
    DroneTargetPose_<id>  (Pose)    - целевая позиция, которую задает Python
    CableForce_<id>       (Float32) - натяжение троса, Н
и сохраняет их в CSV, а в конце печатает сводку характеристик.

Использование:
    python swarm_check.py                      # проверка связи + 1 опрос
    python swarm_check.py --drones 6 --duration 60 --csv flight.csv
    python swarm_check.py --port 5555 --rate 20

Unity должна быть в Play Mode, а на сцене должен быть объект с ServerApp
(иначе сервер не запущен и скрипт завершится по таймауту).
"""

import argparse
import csv
import json
import sys
import time

import zmq


class RsmaClient:
    def __init__(self, host, port, timeout_ms):
        self._ctx = zmq.Context.instance()
        self._addr = f"tcp://{host}:{port}"
        self._timeout_ms = timeout_ms
        self._connect()

    def _connect(self):
        # REQ сам добавляет пустой фрейм-разделитель, которого ждет RouterSocket
        self._sock = self._ctx.socket(zmq.REQ)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.setsockopt(zmq.RCVTIMEO, self._timeout_ms)
        self._sock.connect(self._addr)

    def request(self, payload):
        try:
            self._sock.send_string(payload)
            return self._sock.recv_string()
        except zmq.Again:
            # После таймаута REQ-сокет нельзя использовать повторно
            self._sock.close()
            self._connect()
            raise TimeoutError(f"Нет ответа от {self._addr}")

    def get(self, topic_name, topic_type):
        packet = {"Action": "get", "TopicName": topic_name, "TopicType": topic_type, "Data": ""}
        response = json.loads(self.request(json.dumps(packet)))
        if response.get("status") != "ok":
            raise RuntimeError(f"{topic_name}: {response}")
        return json.loads(response["data"])

    def close(self):
        self._sock.close()


def read_pose(client, name):
    pose = client.get(name, "Pose")
    p = pose.get("position") or {}
    return pose.get("timestamp", 0), p.get("x", 0.0), p.get("y", 0.0), p.get("z", 0.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--drones", type=int, default=6, help="количество дронов (numDrones)")
    parser.add_argument("--duration", type=float, default=0.0, help="длительность записи, с (0 - один опрос)")
    parser.add_argument("--rate", type=float, default=10.0, help="частота опроса, Гц")
    parser.add_argument("--csv", help="файл для сохранения телеметрии")
    parser.add_argument("--timeout", type=int, default=2000, help="таймаут ответа, мс")
    args = parser.parse_args()

    client = RsmaClient(args.host, args.port, args.timeout)
    try:
        status = client.request("GetServerStatus")
    except TimeoutError as e:
        print(f"[FAIL] {e}. Unity в Play Mode? На сцене есть ServerApp?", file=sys.stderr)
        return 1
    print(f"[OK] {status}")

    ids = range(1, args.drones + 1)
    header = ["t"]
    for i in ids:
        header += [f"x{i}", f"y{i}", f"z{i}", f"tx{i}", f"ty{i}", f"tz{i}", f"F{i}"]

    rows = []
    t0 = time.time()
    period = 1.0 / args.rate
    while True:
        row = [round(time.time() - t0, 3)]
        for i in ids:
            _, x, y, z = read_pose(client, f"DronePose_{i}")
            _, tx, ty, tz = read_pose(client, f"DroneTargetPose_{i}")
            force = client.get(f"CableForce_{i}", "Float32").get("value", 0.0)
            row += [x, y, z, tx, ty, tz, force]
        rows.append(row)
        if time.time() - t0 >= args.duration:
            break
        time.sleep(max(0.0, period - (time.time() - t0 - row[0])))
    client.close()

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(header)
            writer.writerows(rows)
        print(f"Сохранено строк: {len(rows)} -> {args.csv}")

    print_summary(rows, ids)
    return 0


def print_summary(rows, ids):
    print(f"\n{'id':>3} {'высота, м':>10} {'ошибка, м':>10} {'ошибка max':>10} {'F ср, Н':>8} {'F max, Н':>9}")
    for k, i in enumerate(ids):
        b = 1 + k * 7
        heights, errors, forces = [], [], []
        for r in rows:
            x, y, z, tx, ty, tz, force = r[b:b + 7]
            heights.append(y)
            forces.append(force)
            # Нулевая цель Quadrocopter игнорирует - значит Python ее еще не задал
            if (tx, ty, tz) != (0.0, 0.0, 0.0):
                errors.append(((x - tx) ** 2 + (y - ty) ** 2 + (z - tz) ** 2) ** 0.5)
        err = f"{sum(errors) / len(errors):10.3f} {max(errors):10.3f}" if errors else f"{'-':>10} {'-':>10}"
        print(f"{i:>3} {heights[-1]:10.2f} {err} {sum(forces) / len(forces):8.1f} {max(forces):9.1f}")


if __name__ == "__main__":
    sys.exit(main())
