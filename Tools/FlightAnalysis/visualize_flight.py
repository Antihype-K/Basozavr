"""
Визуализация результатов полета, записанных компонентом TransformWriter (Unity).

Формат CSV (разделитель ';', десятичная запятая):
    <имя>;x;y;z;time;<имя2>;x;y;z;time;...
    ;0,05;0,11;2,14;0;;...

Ось Y в Unity направлена вверх, поэтому высота = y, горизонтальная плоскость = (x, z).

Использование:
    python visualize_flight.py ../../Assets/hhh.csv
    python visualize_flight.py flight.csv --object Мотор --session 2 --save flight.png --no-show
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

FIELDS_PER_OBJECT = 5  # имя/пусто, x, y, z, time


def _to_float(value):
    return float(value.strip().replace(",", "."))


def load_flight_csv(path):
    """Возвращает словарь {имя объекта: массив Nx4 (t, x, y, z)}."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        lines = [line.rstrip("\r\n") for line in f if line.strip()]

    if not lines:
        raise ValueError(f"Файл {path} пуст")

    header = lines[0].split(";")
    names = [header[i].strip() or f"object_{i // FIELDS_PER_OBJECT}"
             for i in range(0, len(header) - 1, FIELDS_PER_OBJECT)]
    rows = {name: [] for name in names}

    skipped = 0
    for line in lines[1:]:
        cells = line.split(";")
        try:
            for k, name in enumerate(names):
                base = k * FIELDS_PER_OBJECT
                x, y, z, t = (_to_float(c) for c in cells[base + 1:base + 5])
                rows[name].append((t, x, y, z))
        except (ValueError, IndexError):
            # Последняя строка часто обрезана, если запись остановили не через "Stop writing"
            skipped += 1

    if skipped:
        print(f"Пропущено некорректных строк: {skipped}", file=sys.stderr)

    return {name: split_sessions(np.array(data)) for name, data in rows.items() if data}


def split_sessions(data):
    """TransformWriter дописывает в существующий файл, и время каждой новой записи
    начинается с нуля. Делим данные на отдельные полеты по сбросу времени."""
    resets = np.where(np.diff(data[:, 0]) < 0)[0] + 1
    return np.split(data, resets)


def compute_characteristics(data):
    t, x, y, z = data.T
    pos = np.column_stack((x, y, z))

    vel = np.gradient(pos, t, axis=0)
    speed = np.linalg.norm(vel, axis=1)
    h_speed = np.linalg.norm(vel[:, [0, 2]], axis=1)
    v_speed = vel[:, 1]
    acc = np.linalg.norm(np.gradient(vel, t, axis=0), axis=1)

    steps = np.diff(pos, axis=0)
    path_len = np.linalg.norm(steps, axis=1).sum()
    h_path_len = np.linalg.norm(steps[:, [0, 2]], axis=1).sum()

    stats = {
        "Длительность, с": t[-1] - t[0],
        "Количество точек": len(t),
        "Пройденный путь (3D), м": path_len,
        "Пройденный путь (гориз.), м": h_path_len,
        "Смещение старт-финиш, м": np.linalg.norm(pos[-1] - pos[0]),
        "Высота мин., м": y.min(),
        "Высота макс., м": y.max(),
        "Набор высоты (макс. - старт), м": y.max() - y[0],
        "Скорость средняя, м/с": path_len / (t[-1] - t[0]) if t[-1] > t[0] else 0.0,
        "Скорость макс., м/с": speed.max(),
        "Гориз. скорость макс., м/с": h_speed.max(),
        "Скороподъемность макс., м/с": v_speed.max(),
        "Скорость снижения макс., м/с": -v_speed.min(),
        "Ускорение макс., м/с²": acc.max(),
    }
    series = {"speed": speed, "h_speed": h_speed, "v_speed": v_speed, "acc": acc}
    return stats, series


def print_characteristics(name, stats):
    print(f"\n=== Характеристики полета: {name} ===")
    width = max(len(k) for k in stats)
    for key, value in stats.items():
        text = f"{value:d}" if isinstance(value, (int, np.integer)) else f"{value:.3f}"
        print(f"{key:<{width}}  {text}")


def plot_flight(name, data, stats, series):
    t, x, y, z = data.T

    fig = plt.figure(figsize=(14, 9))
    fig.suptitle(f"Результаты полета: {name}", fontsize=14)

    ax3d = fig.add_subplot(2, 2, 1, projection="3d")
    ax3d.plot(x, z, y, lw=1.2)
    ax3d.scatter(x[0], z[0], y[0], c="green", s=40, label="Старт")
    ax3d.scatter(x[-1], z[-1], y[-1], c="red", s=40, label="Финиш")
    ax3d.set_xlabel("X, м")
    ax3d.set_ylabel("Z, м")
    ax3d.set_zlabel("Высота (Y), м")
    ax3d.set_title("Траектория 3D")
    ax3d.legend()

    ax_top = fig.add_subplot(2, 2, 2)
    ax_top.plot(x, z, lw=1.2)
    ax_top.plot(x[0], z[0], "go", label="Старт")
    ax_top.plot(x[-1], z[-1], "ro", label="Финиш")
    ax_top.set_xlabel("X, м")
    ax_top.set_ylabel("Z, м")
    ax_top.set_title("Вид сверху")
    ax_top.axis("equal")
    ax_top.grid(True, alpha=0.3)
    ax_top.legend()

    ax_alt = fig.add_subplot(2, 2, 3)
    ax_alt.plot(t, y, lw=1.2)
    ax_alt.set_xlabel("Время, с")
    ax_alt.set_ylabel("Высота, м")
    ax_alt.set_title(f"Высота (макс. {stats['Высота макс., м']:.2f} м)")
    ax_alt.grid(True, alpha=0.3)

    ax_spd = fig.add_subplot(2, 2, 4)
    ax_spd.plot(t, series["speed"], lw=1.2, label="Полная")
    ax_spd.plot(t, series["h_speed"], lw=1.0, label="Горизонтальная")
    ax_spd.plot(t, series["v_speed"], lw=1.0, label="Вертикальная")
    ax_spd.set_xlabel("Время, с")
    ax_spd.set_ylabel("Скорость, м/с")
    ax_spd.set_title(f"Скорость (макс. {stats['Скорость макс., м/с']:.2f} м/с)")
    ax_spd.grid(True, alpha=0.3)
    ax_spd.legend()

    fig.tight_layout()
    return fig


def main():
    parser = argparse.ArgumentParser(description="Визуализация результатов полета из CSV TransformWriter")
    parser.add_argument("csv", type=Path, help="путь к CSV-файлу")
    parser.add_argument("--object", help="имя объекта (по умолчанию все объекты из файла)")
    parser.add_argument("--session", type=int, help="номер записи (с 1), если в файле их несколько")
    parser.add_argument("--save", type=Path, help="сохранить графики в PNG (для нескольких объектов к имени добавляется суффикс)")
    parser.add_argument("--no-show", action="store_true", help="не открывать окно с графиками")
    args = parser.parse_args()

    flights = load_flight_csv(args.csv)
    if args.object:
        if args.object not in flights:
            sys.exit(f"Объект '{args.object}' не найден. Доступные: {', '.join(flights)}")
        flights = {args.object: flights[args.object]}

    flights = {
        (name if len(sessions) == 1 else f"{name}, запись {i}"): data
        for name, sessions in flights.items()
        for i, data in enumerate(sessions, 1)
        if args.session is None or i == args.session
    }
    if not flights:
        sys.exit(f"Запись {args.session} не найдена")

    for name, data in flights.items():
        if len(data) < 3:
            print(f"{name}: недостаточно точек для анализа", file=sys.stderr)
            continue
        stats, series = compute_characteristics(data)
        print_characteristics(name, stats)
        fig = plot_flight(name, data, stats, series)
        if args.save:
            suffix = name.replace(", запись ", "_")
            out = args.save if len(flights) == 1 else args.save.with_stem(f"{args.save.stem}_{suffix}")
            fig.savefig(out, dpi=150)
            print(f"Графики сохранены: {out}")

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
