"""
Ступенчатый тест роя: поднять все дроны на заданную высоту, удержать и снять отклик.

Не требует Python-кода управления роем: сам публикует DroneTargetPose_<id>
(текущая позиция дрона + dy по вертикали), записывает позиции и натяжения
и считает характеристики переходного процесса по каждому дрону:
    время нарастания (10->90 %), перерегулирование, время установления (±5 % ступени),
    установившаяся ошибка, натяжение троса (среднее/максимум на удержании).

Использование (Unity в Play Mode, на сцене есть ServerApp):
    python step_test.py --drones 6 --dy 5 --hold 20 --csv step.csv
    python step_test.py --drones 6 --dy 10 --hold 30 --land     # в конце вернуть на старт
"""

import argparse
import csv
import json
import sys
import time

from swarm_check import RsmaClient, read_pose


def publish_target(client, drone_id, x, y, z):
    pose = {"timestamp": int(time.time() * 1000),
            "position": {"x": x, "y": y, "z": z},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}
    packet = {"Action": "publish", "TopicName": f"DroneTargetPose_{drone_id}",
              "TopicType": "Pose", "Data": json.dumps(pose)}
    response = json.loads(client.request(json.dumps(packet)))
    if response.get("status") != "ok":
        raise RuntimeError(f"DroneTargetPose_{drone_id}: {response}")


def step_metrics(t, y, y0, y1):
    """Характеристики отклика y(t) на ступень y0 -> y1."""
    step = y1 - y0
    norm = [(v - y0) / step for v in y]
    t10 = next((ti for ti, n in zip(t, norm) if n >= 0.1), None)
    t90 = next((ti for ti, n in zip(t, norm) if n >= 0.9), None)
    rise = t90 - t10 if t10 is not None and t90 is not None else None
    overshoot = max(0.0, (max(norm) - 1.0) * 100.0)
    settle = None
    for i in range(len(norm)):
        if all(abs(n - 1.0) <= 0.05 for n in norm[i:]):
            settle = t[i]
            break
    tail = y[-max(1, len(y) // 10):]
    sse = abs(y1 - sum(tail) / len(tail))
    return rise, overshoot, settle, sse


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--drones", type=int, default=6)
    parser.add_argument("--dy", type=float, default=5.0, help="высота подъема, м")
    parser.add_argument("--hold", type=float, default=20.0, help="время записи после команды, с")
    parser.add_argument("--rate", type=float, default=20.0, help="частота опроса, Гц")
    parser.add_argument("--csv", help="файл для сохранения телеметрии")
    parser.add_argument("--land", action="store_true", help="после теста вернуть дроны в стартовые точки")
    args = parser.parse_args()

    client = RsmaClient(args.host, args.port, 2000)
    try:
        print(f"[OK] {client.request('GetServerStatus')}")
    except TimeoutError as e:
        print(f"[FAIL] {e}. Unity в Play Mode? На сцене есть ServerApp?", file=sys.stderr)
        return 1

    ids = list(range(1, args.drones + 1))
    start = {i: read_pose(client, f"DronePose_{i}")[1:] for i in ids}
    for i in ids:
        x, y, z = start[i]
        publish_target(client, i, x, y + args.dy, z)
    print(f"Команда: подъем на {args.dy} м, запись {args.hold} с")

    t_log, y_log, f_log = [], {i: [] for i in ids}, {i: [] for i in ids}
    rows = []
    t0 = time.time()
    period = 1.0 / args.rate
    while time.time() - t0 < args.hold:
        t_iter = time.time()
        t = t_iter - t0
        row = [round(t, 3)]
        t_log.append(t)
        for i in ids:
            _, x, y, z = read_pose(client, f"DronePose_{i}")
            force = client.get(f"CableForce_{i}", "Float32").get("value", 0.0)
            y_log[i].append(y)
            f_log[i].append(force)
            row += [x, y, z, force]
        rows.append(row)
        time.sleep(max(0.0, period - (time.time() - t_iter)))

    if args.land:
        for i in ids:
            publish_target(client, i, *start[i])
        print("Дроны возвращены в стартовые точки")
    client.close()

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            header = ["t"]
            for i in ids:
                header += [f"x{i}", f"y{i}", f"z{i}", f"F{i}"]
            writer.writerow(header)
            writer.writerows(rows)
        print(f"Сохранено строк: {len(rows)} -> {args.csv}")

    fmt = lambda v, f: "-" if v is None else format(v, f)
    print(f"\n{'id':>3} {'нараст., с':>10} {'перерег., %':>11} {'устан., с':>9} {'ошибка, м':>9} {'F ср, Н':>8} {'F max, Н':>9}")
    hold_from = len(t_log) // 2  # натяжение считаем по второй половине записи (удержание)
    for i in ids:
        y0 = start[i][1]
        rise, over, settle, sse = step_metrics(t_log, y_log[i], y0, y0 + args.dy)
        hold_f = f_log[i][hold_from:] or [0.0]
        print(f"{i:>3} {fmt(rise, '10.2f')} {over:11.1f} {fmt(settle, '9.2f')} {sse:9.3f} "
              f"{sum(hold_f) / len(hold_f):8.1f} {max(hold_f):9.1f}")
    total = sum(sum(f_log[i][hold_from:]) / max(1, len(f_log[i][hold_from:])) for i in ids)
    print(f"\nСуммарное натяжение на удержании: {total:.1f} Н")
    return 0


if __name__ == "__main__":
    sys.exit(main())
