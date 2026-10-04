"""
Контроллер миссии доставки роя: взлёт -> перенос -> опускание -> отцепка -> возврат -> посадка.

Связь с Unity — NetMQ (порт 5555), топики те же, что у swarm_check.py. Контроллер ведёт общую
цель строя (ограничение скорости и ускорения), каждому дрону отправляет DroneTargetPose_<id>,
перед отцепкой ослабляет тросы и публикует CableRelease_<id>.

    python mission.py --drones 6 --payload-mass 19.8 --dropoff 185.2 95.5
    python mission.py --drones 6 --payload-mass 12 --dropoff 185.2 95.5 --equalize --log mission.csv

Unity: сцена Assets/1.unity запущена (Play или ./Builds/SwarmDelivery/SwarmDelivery.x86_64).
Контроллер запоминает стартовые позиции дронов и груза, поэтому после каждой миссии
рой нужно вернуть на старт (RestartLevel) — или запускать --trips 1.
"""

import argparse
import csv
import json
import math
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/SwarmCheck")
from swarm_check import RsmaClient, read_pose  # noqa: E402

G = 9.81


class Setpoint:
    """
    Общая цель строя: ведётся к точке с ограничением скорости и ускорения и торможением перед точкой.

    Поверх траектории — формирователь входа ZVD (input shaper): команда подаётся тремя импульсами
    (1/4, 1/2, 1/4) с шагом в полпериода колебаний груза, и колебания после разгона/торможения гасят друг друга.
    Период груза на модели ~5,5 с; формирователь устойчив к ошибке периода около ±1 с.
    p — то, что отправляется дронам (после формирователя), raw — траектория до него.
    """

    def __init__(self, position, vmax, amax, shaper_period=0.0, dt=0.05):
        self.raw = list(position)
        self.p = list(position)
        self.v = [0.0, 0.0, 0.0]
        self.vmax, self.amax = vmax, amax
        half = int(round(shaper_period / 2.0 / dt)) if shaper_period > 0 else 0
        self.taps = [(0.25, 0), (0.5, half), (0.25, 2 * half)] if half else [(1.0, 0)]
        self.hist = []

    def fast_mode(self, vmax, amax):
        """Без груза формирователь не нужен: продолжаем с текущего выхода без скачка цели, с большим ускорением."""
        self.raw = list(self.p)
        self.v = [0.0, 0.0, 0.0]
        self.hist = [list(self.raw)]
        self.taps = [(1.0, 0)]
        self.vmax, self.amax = vmax, amax

    def step(self, goal, dt):
        d = [goal[k] - self.raw[k] for k in range(3)]
        dist = math.sqrt(sum(c * c for c in d))
        limit = min(self.vmax, math.sqrt(2.0 * self.amax * dist))
        want = [c / dist * limit for c in d] if dist > 1e-6 else [0.0, 0.0, 0.0]
        dv = [want[k] - self.v[k] for k in range(3)]
        dvn = math.sqrt(sum(c * c for c in dv))
        if dvn > self.amax * dt:
            dv = [c * self.amax * dt / dvn for c in dv]
        self.v = [self.v[k] + dv[k] for k in range(3)]
        move = [c * dt for c in self.v]
        if math.sqrt(sum(c * c for c in move)) >= dist:
            self.raw, self.v = list(goal), [0.0, 0.0, 0.0]
        else:
            self.raw = [self.raw[k] + move[k] for k in range(3)]
        self.hist.append(list(self.raw))
        self.p = [sum(w * self.hist[max(0, len(self.hist) - 1 - delay)][k] for w, delay in self.taps) for k in range(3)]
        return math.sqrt(sum((goal[k] - self.p[k]) ** 2 for k in range(3)))  # расстояние от выхода формирователя до цели


class Mission:
    def __init__(self, args):
        self.a = args
        self.client = RsmaClient(args.host, args.port, 2000)
        self.ids = list(range(1, args.drones + 1))
        self.log_rows = []
        self.t0 = time.time()
        self.released = False
        self.eq = {i: 0.0 for i in self.ids}  # поправка высоты при выравнивании натяжений
        # ускорение: либо задано явно, либо из допустимой раскачки (модель: пик раскачки ~ 12.5 °·с²/м × ускорение)
        self.accel = args.accel if args.max_swing is None else max(0.1, min(1.0, args.max_swing / 12.5))
        if args.max_swing is not None and args.no_shaper:
            self.accel = max(0.1, min(1.0, args.max_swing / 18.0))  # без формирователя пик выше ~ 18 °·с²/м

    # --- обмен с Unity -------------------------------------------------
    def drone_pos(self, i):
        return read_pose(self.client, f"DronePose_{i}")[1:]

    def payload(self):
        return read_pose(self.client, "PayloadPose")[1:]

    def tensions(self):
        return [self.client.get(f"CableForce_{i}", "Float32").get("value", 0.0) for i in self.ids]

    def send_target(self, i, pos):
        pose = {"timestamp": int(time.time() * 1000), "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}
        self._publish(f"DroneTargetPose_{i}", "Pose", pose)

    def release_cables(self):
        for i in self.ids:
            self._publish(f"CableRelease_{i}", "Float32", {"value": 1.0, "timestamp": int(time.time() * 1000)})
        self.released = True

    def _publish(self, name, kind, data):
        packet = {"Action": "publish", "TopicName": name, "TopicType": kind, "Data": json.dumps(data)}
        r = json.loads(self.client.request(json.dumps(packet)))
        if r.get("status") != "ok":
            raise RuntimeError(f"{name}: {r}")

    # --- миссия -------------------------------------------------------
    def run(self):
        a = self.a
        start = {i: self.drone_pos(i) for i in self.ids}
        pay0 = self.payload()
        cx = sum(p[0] for p in start.values()) / len(start)
        cz = sum(p[2] for p in start.values()) / len(start)
        cy = sum(p[1] for p in start.values()) / len(start)
        sp = Setpoint((cx, cy, cz), a.speed, self.accel, 0.0 if a.no_shaper else a.shaper_period, 1.0 / a.rate)
        weight = a.payload_mass * G
        dt = 1.0 / a.rate
        print(f"Старт: центр строя ({cx:.1f}, {cy:.1f}, {cz:.1f}), груз ({pay0[0]:.1f}, {pay0[1]:.1f}, {pay0[2]:.1f})")

        # (этап, цель центра строя, условие завершения)
        stages = [
            ("Взлёт", lambda: (cx, a.height, cz), lambda d, s: d < 0.15 and self.payload()[1] > pay0[1] + 1.0),
            ("Перенос груза", lambda: (a.dropoff[0], a.height, a.dropoff[1]), lambda d, s: d < 0.1 and self.payload_error() < self.a.tolerance),
            ("Опускание", self.lowering_goal, self.lowering_done),
            ("Отцепка", lambda: tuple(sp.p), None),
            ("Возврат на базу", lambda: (cx, a.height, cz), lambda d, s: d < 0.15),
            ("Посадка", lambda: (cx, cy, cz), lambda d, s: d < 0.1),
        ]
        self._sp, self._pay0, self._weight, self._cy = sp, pay0, weight, cy
        for name, goal, done in stages:
            print(f"Этап: {name}")
            t_stage = time.time()
            if name == "Отцепка":
                self.release_cables()
                sp.fast_mode(a.speed, 1.0)
                time.sleep(0.5)
                continue
            while True:
                t_iter = time.time()
                g = goal()
                dist = sp.step(g, dt)
                self.command(start, sp.p, cx, cy, cz)
                self.record(name, sp.p)
                if done(dist, sp):
                    break
                if time.time() - t_stage > a.stage_timeout:
                    print(f"  [WARN] этап '{name}' не завершился за {a.stage_timeout:.0f} с — продолжаю")
                    break
                time.sleep(max(0.0, dt - (time.time() - t_iter)))
        self.summary()

    def payload_error(self):
        """Расстояние от груза до точки выгрузки в горизонтальной плоскости, м."""
        px, _, pz = self.payload()
        return math.hypot(px - self.a.dropoff[0], pz - self.a.dropoff[1])

    def lowering_goal(self):
        # опускаем строй до касания; затем ещё немного, пока тросы не ослабнут
        x, y, z = self._sp.raw
        return (x, max(self._cy, y - 1.0), z)  # не ниже стартовой высоты дронов

    def lowering_done(self, dist, sp):
        pay = self.payload()
        t = sum(self.tensions())
        on_ground = pay[1] <= self._pay0[1] + 0.3 and self.payload_error() < 2 * self.a.tolerance
        slack = t < self.a.slack_fraction * self._weight
        return on_ground and slack

    def command(self, start, c, cx, cy, cz):
        shift = (c[0] - cx, c[1] - cy, c[2] - cz)
        if self.a.equalize and not self.released:
            self.update_equalizer()
        for i in self.ids:
            s = start[i]
            self.send_target(i, (s[0] + shift[0], s[1] + shift[1] + self.eq[i], s[2] + shift[2]))

    def update_equalizer(self):
        """Перегруженный трос -> дрон опускается (трос провисает), недогруженный поднимается."""
        ten = self.tensions()
        mean = sum(ten) / len(ten)
        if mean < 1.0:
            return
        for i, t in zip(self.ids, ten):
            self.eq[i] = max(-1.5, min(1.5, self.eq[i] - 0.02 * (t - mean) / self.a.rate))

    def record(self, stage, sp):
        px, py, pz = self.payload()
        ten = self.tensions()
        self.log_rows.append([round(time.time() - self.t0, 2), stage, px, py, pz, sum(ten), min(ten), max(ten)])

    def summary(self):
        rows = self.log_rows
        dx, dz = self.a.dropoff
        drop = [r for r in rows if r[1] == "Опускание"]
        if drop:
            e = math.hypot(drop[-1][2] - dx, drop[-1][4] - dz)
            print(f"\nТочность выгрузки: {e:.2f} м от точки ({dx}, {dz})")
        print(f"Время миссии: {rows[-1][0]:.1f} с, груз макс. высота {max(r[3] for r in rows):.1f} м, "
              f"макс. суммарное натяжение {max(r[5] for r in rows):.0f} Н")
        if self.a.log:
            with open(self.a.log, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["t", "stage", "px", "py", "pz", "T_sum", "T_min", "T_max"])
                w.writerows(rows)
            print(f"Лог: {self.a.log}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--drones", type=int, default=6)
    ap.add_argument("--payload-mass", type=float, default=12.0, help="масса груза, кг (для проверки ослабления тросов)")
    ap.add_argument("--dropoff", type=float, nargs=2, metavar=("X", "Z"), required=True, help="точка выгрузки")
    ap.add_argument("--height", type=float, default=13.0, help="высота дронов при переносе, м")
    ap.add_argument("--speed", type=float, default=4.6, help="макс. скорость, м/с")
    ap.add_argument("--accel", type=float, default=0.3, help="макс. ускорение, м/с² (меньше — меньше раскачка, дольше полёт)")
    ap.add_argument("--max-swing", type=float, default=None, metavar="DEG",
                    help="допустимая пиковая раскачка груза, градусы: ускорение подбирается по модели (заменяет --accel)")
    ap.add_argument("--shaper-period", type=float, default=5.5, help="период колебаний груза для формирователя, с")
    ap.add_argument("--no-shaper", action="store_true", help="отключить формирователь входа")
    ap.add_argument("--rate", type=float, default=20.0, help="частота команд, Гц")
    ap.add_argument("--slack-fraction", type=float, default=0.15, help="отцепка, когда суммарное натяжение < доли веса груза")
    ap.add_argument("--tolerance", type=float, default=0.25, help="допуск по положению груза в точке выгрузки, м")
    ap.add_argument("--stage-timeout", type=float, default=120.0, help="максимум на этап, с")
    ap.add_argument("--equalize", action="store_true", help="выравнивать натяжения тросов (точнее по нагрузке, но больше раскачка)")
    ap.add_argument("--log", help="CSV с логом миссии")
    args = ap.parse_args()
    try:
        mission = Mission(args)
        print(mission.client.request("GetServerStatus"))
        mission.run()
    except TimeoutError as e:
        print(f"[FAIL] {e}. Unity запущена, сцена Assets/1.unity?", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
