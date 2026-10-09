"""
Запись полета встроенной миссии (run.py) и отчет-график после успешной доставки груза.

FlightRecorder копит телеметрию из RSMA (этап миссии, положение груза, натяжение тросов);
delivered становится True, когда этап «Выгрузка» завершился. save() пишет CSV и PNG
с четырьмя графиками: путь груза сверху, высота, скорость, натяжение тросов.
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
    t: float
    phase: str
    x: float
    y: float
    z: float
    distance: float
    tension: float


class FlightRecorder:
    def __init__(self):
        self.samples: list[Sample] = []
        self.finish: tuple[float, float, float] | None = None
        self.delivered_at: float | None = None
        self._seen_unload = False

    def add(self, t: float, phase: str, position, distance: float, tension: float, finish=None) -> None:
        self.samples.append(Sample(t, phase, position.x, position.y, position.z, distance, tension))
        if finish is not None:
            self.finish = (finish.x, finish.y, finish.z)
        if phase == UNLOAD_PHASE:
            self._seen_unload = True
        elif self._seen_unload and self.delivered_at is None:
            self.delivered_at = t  # выгрузка закончилась: груз доставлен

    @property
    def delivered(self) -> bool:
        return self.delivered_at is not None

    # --- Итоги ---

    def _until_delivery(self) -> list[Sample]:
        if self.delivered_at is None:
            return self.samples
        return [s for s in self.samples if s.t <= self.delivered_at]

    def speeds(self, samples: list[Sample]) -> list[float]:
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
        return {
            "time": s[-1].t - s[0].t,
            "path": path,
            "max_speed": max(self.speeds(s)),
            "max_tension": max(x.tension for x in s),
            "max_height": max(x.y for x in s) - s[0].y,
        }

    # --- Сохранение ---

    def save_csv(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t", "phase", "payload_x", "payload_y", "payload_z", "dist_to_delivery", "tension_sum"])
            for s in self.samples:
                w.writerow([f"{s.t:.2f}", s.phase, f"{s.x:.3f}", f"{s.y:.3f}", f"{s.z:.3f}",
                            f"{s.distance:.3f}", f"{s.tension:.1f}"])
        return path

    def plot(self, path: Path):
        """Строит отчет до момента доставки, сохраняет PNG и возвращает figure."""
        import matplotlib.pyplot as plt

        s = self._until_delivery()
        t0 = s[0].t
        t = [x.t - t0 for x in s]
        ground = s[0].y
        info = self.summary()

        fig, axes = plt.subplots(2, 2, figsize=(14, 9), facecolor=SURFACE)
        title = "Груз доставлен" if self.delivered else "Полет (доставка не завершена)"
        fig.suptitle(f"{title}: {info['time']:.0f} с, путь {info['path']:.0f} м, "
                     f"макс. скорость {info['max_speed']:.1f} м/с, пик натяжения {info['max_tension']:.0f} Н",
                     color=TEXT, fontsize=14, fontweight="bold")

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
            (axes[1, 0], self.speeds(s), "Скорость груза, м/с"),
            (axes[1, 1], [x.tension for x in s], "Суммарное натяжение тросов, Н"),
        ]
        changes = [(t[i], s[i].phase) for i in range(len(s)) if i == 0 or s[i].phase != s[i - 1].phase]
        for ax, values, label in series:
            ax.plot(t, values, color=SERIES, linewidth=2)
            ax.set_title(label, color=TEXT, loc="left")
            ax.set_xlabel("Время, с", color=TEXT_MUTED)
            top = max(values) if values else 1.0
            for tc, _phase in changes:
                ax.axvline(tc, color=TEXT_MUTED, linewidth=0.8, alpha=0.5)
            if ax is axes[0, 1]:  # подписи этапов — на одном графике, чтобы не загромождать
                for tc, phase in changes:
                    ax.text(tc, top, f" {phase}", rotation=90, va="top", ha="left", fontsize=8, color=TEXT_MUTED)

        fig.tight_layout(rect=(0, 0, 1, 0.95))
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=110, facecolor=SURFACE)
        return fig


def report_paths(log_dir: Path) -> tuple[Path, Path]:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return log_dir / f"delivery_{stamp}.csv", log_dir / f"delivery_{stamp}.png"
