"""
Запись полета встроенной миссии (run.py) и отчет-график после успешной доставки груза.

FlightRecorder копит телеметрию из RSMA: этап миссии (MissionStatus), положение груза
(PayloadPose), раскачку, натяжения и скорость (SwarmTelemetry). delivered становится True,
когда этап «Выгрузка» завершился. save_csv() / plot() пишут CSV и PNG-отчет.
"""

import csv
import math
import time
from dataclasses import dataclass
from pathlib import Path

UNLOAD_PHASE = "Выгрузка"

# Палитра (dataviz reference palette, светлая тема): одна серия на график
SERIES = "#2a78d6"
ACCENT = "#eb6834"  # площадка доставки (оранжевая, как в сцене)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e4e3df"


@dataclass
class Sample:
    t: float  # время миссии (по часам симуляции, если RSMA его сообщает), с
    phase: str
    x: float
    y: float
    z: float
    distance: float  # до площадки по горизонтали, м
    tension: float  # суммарное натяжение тросов, Н
    swing: float | None = None  # раскачка, градусы
    speed: float | None = None  # скорость груза, м/с
    min_tension: float | None = None
    max_tension: float | None = None


class FlightRecorder:
    def __init__(self):
        self.samples: list[Sample] = []
        self.finish: tuple[float, float, float] | None = None
        self.delivered_at: float | None = None
        self.parameters: dict = {}  # параметры миссии — для подписи отчета
        self._seen_unload = False

    def add(self, t: float, phase: str, position, distance: float, tension: float, finish=None,
            telemetry=None) -> None:
        sample = Sample(t, phase, position.x, position.y, position.z, distance, tension)
        if telemetry is not None:
            sample.t = telemetry.missionTime
            sample.tension = telemetry.totalTension
            sample.swing = telemetry.swingAngle
            sample.speed = telemetry.payloadSpeed
            sample.min_tension = telemetry.minTension
            sample.max_tension = telemetry.maxTension
        if self.samples and sample.t <= self.samples[-1].t:
            return  # тот же кадр симуляции
        self.samples.append(sample)
        if finish is not None:
            self.finish = (finish.x, finish.y, finish.z)
        if phase == UNLOAD_PHASE:
            self._seen_unload = True
        elif self._seen_unload and self.delivered_at is None:
            self.delivered_at = sample.t  # выгрузка закончилась: груз доставлен

    @property
    def delivered(self) -> bool:
        return self.delivered_at is not None

    # --- Итоги ---

    def _until_delivery(self) -> list[Sample]:
        if self.delivered_at is None:
            return self.samples
        return [s for s in self.samples if s.t <= self.delivered_at]

    def speeds(self, samples: list[Sample]) -> list[float]:
        """Скорость груза: из RSMA, а если ее нет — по разности положений."""
        if samples and all(s.speed is not None for s in samples):
            return [s.speed for s in samples]
        out = [0.0]
        for a, b in zip(samples, samples[1:], strict=False):
            dt = b.t - a.t
            out.append(math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) / dt if dt > 0 else out[-1])
        return out

    def summary(self) -> dict:
        s = self._until_delivery()
        if not s:
            return {}
        path = sum(math.dist((a.x, a.z), (b.x, b.z)) for a, b in zip(s, s[1:], strict=False))
        swings = [x.swing for x in s if x.swing is not None]
        transport = [x.swing for x in s if x.swing is not None and x.phase not in ("Натяжение тросов",)]
        return {
            "time": s[-1].t - s[0].t,
            "path": path,
            "max_speed": max(self.speeds(s)),
            "max_tension": max(x.tension for x in s),
            "max_cable": max((x.max_tension for x in s if x.max_tension is not None), default=None),
            "max_height": max(x.y for x in s) - s[0].y,
            "max_swing": max(transport, default=None) if transport else (max(swings) if swings else None),
            "landing_error": (math.hypot(s[-1].x - self.finish[0], s[-1].z - self.finish[2])
                              if self.finish else None),
        }

    # --- Сохранение ---

    def save_csv(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)

        def fmt(v, digits):
            return "" if v is None else f"{v:.{digits}f}"

        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t", "phase", "payload_x", "payload_y", "payload_z", "dist_to_delivery",
                        "tension_sum", "tension_min", "tension_max", "swing_deg", "payload_speed"])
            for s in self.samples:
                w.writerow([f"{s.t:.2f}", s.phase, f"{s.x:.3f}", f"{s.y:.3f}", f"{s.z:.3f}", f"{s.distance:.3f}",
                            f"{s.tension:.1f}", fmt(s.min_tension, 1), fmt(s.max_tension, 1),
                            fmt(s.swing, 2), fmt(s.speed, 3)])
        return path

    def plot(self, path: Path):
        """Строит отчет до момента доставки, сохраняет PNG и возвращает figure."""
        import matplotlib.pyplot as plt

        s = self._until_delivery()
        t0 = s[0].t
        t = [x.t - t0 for x in s]
        ground = s[0].y
        info = self.summary()

        fig, axes = plt.subplots(2, 3, figsize=(17, 9.5), facecolor=SURFACE)
        title = "Груз доставлен" if self.delivered else "Полет (доставка не завершена)"
        headline = f"{title}: {info['time']:.0f} с, путь {info['path']:.0f} м"
        if info.get("max_swing") is not None:
            headline += f", макс. раскачка {info['max_swing']:.1f}°"
        fig.suptitle(headline, color=TEXT, fontsize=15, fontweight="bold")

        for ax in axes.flat:
            ax.set_facecolor(SURFACE)
            ax.grid(True, color=GRID, linewidth=0.8)
            ax.tick_params(colors=TEXT_MUTED, labelsize=9)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            for side in ("left", "bottom"):
                ax.spines[side].set_color(GRID)

        # 1. Вид сверху: путь груза, база и площадка
        ax = axes[0, 0]
        ax.plot([x.x for x in s], [x.z for x in s], color=SERIES, linewidth=2)
        ax.plot(s[0].x, s[0].z, "o", color=TEXT, markersize=8)
        ax.annotate("База", (s[0].x, s[0].z), xytext=(8, 8), textcoords="offset points", color=TEXT)
        if self.finish is not None:
            ax.plot(self.finish[0], self.finish[2], "s", color=ACCENT, markersize=10)
            ax.annotate("Площадка", (self.finish[0], self.finish[2]), xytext=(8, -14),
                        textcoords="offset points", color=TEXT)
        ax.set_title("Путь груза (вид сверху)", color=TEXT, loc="left")
        ax.set_xlabel("X, м", color=TEXT_MUTED)
        ax.set_ylabel("Z, м", color=TEXT_MUTED)
        ax.set_aspect("equal", adjustable="datalim")

        series = [
            (axes[0, 1], [x.y - ground for x in s], "Высота груза над базой, м"),
            (axes[0, 2], self.speeds(s), "Скорость груза, м/с"),
            (axes[1, 1], [x.tension for x in s], "Суммарное натяжение тросов, Н"),
        ]
        swings = [x.swing for x in s]
        if all(v is not None for v in swings):
            series.append((axes[1, 0], swings, "Раскачка груза (отклонение тросов), °"))
        else:
            axes[1, 0].text(0.5, 0.5, "Раскачку сообщает RSMA:\nпересоберите сцену (run.py --build)",
                            ha="center", va="center", color=TEXT_MUTED, transform=axes[1, 0].transAxes)
            axes[1, 0].set_title("Раскачка груза, °", color=TEXT, loc="left")

        changes = [(t[i], s[i].phase) for i in range(len(s)) if i == 0 or s[i].phase != s[i - 1].phase]
        for ax, values, label in series:
            ax.plot(t, values, color=SERIES, linewidth=2)
            ax.set_title(label, color=TEXT, loc="left")
            ax.set_xlabel("Время миссии, с", color=TEXT_MUTED)
            for tc, _phase in changes:
                ax.axvline(tc, color=TEXT_MUTED, linewidth=0.8, alpha=0.5)
        top = max(series[0][1]) if series[0][1] else 1.0
        for tc, phase in changes:  # подписи этапов — на одном графике, чтобы не загромождать
            axes[0, 1].text(tc, top, f" {phase}", rotation=90, va="top", ha="left", fontsize=8, color=TEXT_MUTED)

        # 6. Итоги и параметры
        ax = axes[1, 2]
        ax.axis("off")
        rows = [("Время доставки", f"{info['time']:.1f} с"), ("Путь груза", f"{info['path']:.1f} м"),
                ("Макс. скорость", f"{info['max_speed']:.2f} м/с"),
                ("Макс. высота", f"{info['max_height']:.1f} м")]
        if info.get("max_swing") is not None:
            rows.append(("Макс. раскачка", f"{info['max_swing']:.1f}°"))
        rows.append(("Пик Σ натяжения", f"{info['max_tension']:.0f} Н"))
        if info.get("max_cable") is not None:
            rows.append(("Пик на один трос", f"{info['max_cable']:.0f} Н"))
        if info.get("landing_error") is not None:
            rows.append(("Промах по площадке", f"{info['landing_error']:.2f} м"))
        for section in ("delivery", "environment"):
            for k, v in self.parameters.get(section, {}).items():
                if k != "externalControl":
                    rows.append((PARAMETER_NAMES.get(k, k), json_value(v)))
        ax.set_title("Итоги", color=TEXT, loc="left")
        for i, (name, value) in enumerate(rows):
            y = 0.95 - i * 0.075
            ax.text(0.0, y, name, color=TEXT_MUTED, fontsize=10, transform=ax.transAxes)
            ax.text(1.0, y, value, color=TEXT, fontsize=10, ha="right", transform=ax.transAxes)

        fig.tight_layout(rect=(0, 0, 1, 0.95))
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=110, facecolor=SURFACE)
        return fig


PARAMETER_NAMES = {
    "cruiseSpeed": "Скорость, м/с", "climbSpeed": "Скорость подъема, м/с", "acceleration": "Ускорение, м/с²",
    "climbAcceleration": "Ускорение подъема, м/с²", "cruiseHeight": "Высота перелета, м",
    "dropHeight": "Высота выгрузки, м", "unloadTime": "Выгрузка, с", "hoverTime": "Зависание, с",
    "loop": "Повтор рейсов", "releasePayload": "Отцепка груза", "positionKp": "ПИД Kp", "positionKi": "ПИД Ki",
    "positionKd": "ПИД Kd", "basePosition": "База (X, Z)", "deliveryPosition": "Площадка (X, Z)",
    "numDrones": "Дронов", "payloadMass": "Масса груза, кг", "cableLength": "Длина троса, м",
    "radius": "Радиус строя, м", "cableStiffness": "Жесткость троса, Н/м", "windSpeed": "Ветер, м/с",
    "gustAmplitude": "Порывы, м/с", "windDirection": "Направление ветра", "failDroneId": "Отказ дрона №",
    "failTime": "Время отказа, с",
}


def json_value(v) -> str:
    if isinstance(v, dict) and {"x", "z"} <= set(v):
        return f"({v['x']:g}, {v['z']:g})"
    if isinstance(v, bool):
        return "да" if v else "нет"
    return f"{v:g}" if isinstance(v, float) else str(v)


def report_paths(log_dir: Path) -> tuple[Path, Path]:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return log_dir / f"delivery_{stamp}.csv", log_dir / f"delivery_{stamp}.png"
