"""
4-панельный дашборд телеметрии полета.

    python visualize.py                         # последний лог из logs/
    python visualize.py logs/flight_log_X.csv   # конкретный файл
    python visualize.py --save report.png       # сохранить в файл без окна
"""

import argparse
import glob
import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd


def find_latest_log(log_dir: str = "logs") -> str | None:
    """Самый свежий flight_log_*.csv (по времени изменения)."""
    log_files = glob.glob(os.path.join(log_dir, "*.csv"))
    return max(log_files, key=os.path.getmtime) if log_files else None


def plot_flight(df: pd.DataFrame, title: str):
    """Строит 4-панельный дашборд и возвращает figure."""
    import matplotlib.pyplot as plt

    # Определяем количество дронов по колонкам в CSV
    drone_cols = [c for c in df.columns if c.startswith("drone_") and c.endswith("_x")]
    num_drones = len(drone_cols)
    print(f"[Visualizer] Обнаружено дронов в логе: {num_drones}")

    # Создаем единое окно 2x2
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"Анализ полета роя: {title}", fontsize=14, fontweight="bold")

    # Палитра цветов для дронов
    colors = plt.cm.tab10(np.linspace(0, 1, max(num_drones, 6)))

    # -------------------------------------------------------------------------
    # 1. 3D ТРАЕКТОРИЯ (Слева вверху)
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')

    # Траектории всех дронов
    for d_id in range(1, num_drones + 1):
        ax1.plot(
            df[f'drone_{d_id}_x'], df[f'drone_{d_id}_y'], df[f'drone_{d_id}_z'],
            label=f'Дрон {d_id}', color=colors[d_id - 1], alpha=0.6, linewidth=1.2
        )

    # Траектория груза (выделена толстой красной линией)
    ax1.plot(
        df['payload_x'], df['payload_y'], df['payload_z'],
        label='Груз (Payload)', color='red', linewidth=2.5
    )

    # Точки старта и финиша груза
    ax1.scatter(df['payload_x'].iloc[0], df['payload_y'].iloc[0], df['payload_z'].iloc[0], color='green', s=60, label='Старт')
    ax1.scatter(df['payload_x'].iloc[-1], df['payload_y'].iloc[-1], df['payload_z'].iloc[-1], color='black', marker='X', s=80, label='Финиш')

    ax1.set_title("3D Траектория движения роя и груза")
    ax1.set_xlabel("X [м]")
    ax1.set_ylabel("Y [м]")
    ax1.set_zlabel("Z [м]")
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True)

    # -------------------------------------------------------------------------
    # 2. ПРОФИЛЬ ВЫСОТЫ Z (Справа вверху)
    # -------------------------------------------------------------------------
    ax2 = fig.add_subplot(2, 2, 2)

    # Высота каждого дрона
    for d_id in range(1, num_drones + 1):
        ax2.plot(df['step'], df[f'drone_{d_id}_z'], color=colors[d_id - 1], alpha=0.4, linestyle='--')

    # Высота груза и целевая уставка
    ax2.plot(df['step'], df['payload_z'], color='red', linewidth=2, label='Высота груза (Z)')
    if 'target_drone_z' in df.columns:
        ax2.plot(df['step'], df['target_drone_z'], color='black', linestyle=':', label='Уставка Z (Дроны)')

    ax2.set_title("Изменение высоты (Z) по шагам")
    ax2.set_xlabel("Шаг симуляции (step)")
    ax2.set_ylabel("Высота Z [м]")
    ax2.legend(loc='lower right', fontsize=9)
    ax2.grid(True)

    # -------------------------------------------------------------------------
    # 3. НАТЯЖЕНИЕ ТРОСОВ (Слева внизу)
    # -------------------------------------------------------------------------
    ax3 = fig.add_subplot(2, 2, 3)

    # Сила натяжения по каждому дрону
    for d_id in range(1, num_drones + 1):
        col_name = f'cable_force_{d_id}'
        if col_name in df.columns:
            ax3.plot(df['step'], df[col_name], color=colors[d_id - 1], alpha=0.5, label=f'Трос {d_id}')

    # Среднее натяжение
    if 'avg_cable_tension' in df.columns:
        ax3.plot(df['step'], df['avg_cable_tension'], color='purple', linewidth=2, label='Среднее натяжение')

    ax3.set_title("Динамика натяжения тросов (Cable Tension)")
    ax3.set_xlabel("Шаг симуляции (step)")
    ax3.set_ylabel("Сила [Н]")
    ax3.legend(loc='upper right', fontsize=8, ncol=2)
    ax3.grid(True)

    # -------------------------------------------------------------------------
    # 4. ВИД СВЕРХУ XY (Справа внизу)
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(2, 2, 4)

    # Горизонтальное движение дронов
    for d_id in range(1, num_drones + 1):
        ax4.plot(df[f'drone_{d_id}_x'], df[f'drone_{d_id}_y'], color=colors[d_id - 1], alpha=0.5, linewidth=1)

    # Движение груза
    ax4.plot(df['payload_x'], df['payload_y'], color='red', linewidth=2, label='Траектория груза')
    ax4.scatter(df['payload_x'].iloc[0], df['payload_y'].iloc[0], color='green', s=60, zorder=5)
    ax4.scatter(df['payload_x'].iloc[-1], df['payload_y'].iloc[-1], color='black', marker='X', s=80, zorder=5)

    ax4.set_title("Плоскость XY (Вид сверху)")
    ax4.set_xlabel("X [м]")
    ax4.set_ylabel("Y [м]")
    ax4.axis('equal')  # Сохраняем пропорции 1:1 для честной формы формации
    ax4.legend(loc='lower right', fontsize=9)
    ax4.grid(True)

    # Оптимизация отступов
    fig.tight_layout()
    return fig


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Дашборд телеметрии полета роя")
    parser.add_argument("log", nargs="?", help="CSV-лог (по умолчанию — самый свежий в --log-dir)")
    parser.add_argument("--log-dir", default=str(Path(__file__).resolve().parent.parent / "logs"),
                        help="папка с логами (по умолчанию Python/logs)")
    parser.add_argument("--save", metavar="FILE", help="сохранить дашборд в файл (png/pdf/svg) вместо показа окна")
    args = parser.parse_args(argv)

    log_path = args.log or find_latest_log(args.log_dir)
    if not log_path or not os.path.exists(log_path):
        print(f"[Visualizer] Ошибка: файлы логов в папке '{args.log_dir}/' не найдены!")
        return 1

    print(f"[Visualizer] Загрузка телеметрии из файла: {log_path}")
    df = pd.read_csv(log_path)
    if df.empty:
        print("[Visualizer] Ошибка: лог пустой")
        return 1

    if args.save:
        matplotlib.use("Agg")
    fig = plot_flight(df, os.path.basename(log_path))

    if args.save:
        fig.savefig(args.save, dpi=120)
        print(f"[Visualizer] Дашборд сохранен: {args.save}")
    else:
        import matplotlib.pyplot as plt
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
