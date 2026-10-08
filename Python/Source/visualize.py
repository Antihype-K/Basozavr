import glob
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def visualize_latest_flight():
    # 1. Поиск последнего CSV файла в папке logs/
    log_files = sorted(glob.glob("logs/*.csv"))
    if not log_files:
        print("[Visualizer] Ошибка: Файлы логов в папке 'logs/' не найдены!")
        return

    latest_log = log_files[-1]
    print(f"[Visualizer] Загрузка телеметрии из файла: {latest_log}")

    df = pd.read_csv(latest_log)

    # Определяем количество дронов по колонкам в CSV
    drone_cols = [c for c in df.columns if c.startswith("drone_") and c.endswith("_x")]
    num_drones = len(drone_cols)
    print(f"[Visualizer] Обнаружено дронов в логе: {num_drones}")

    # Создаем единое окно 2x2
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"Анализ полета роя: {os.path.basename(latest_log)}", fontsize=14, fontweight="bold")

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
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    visualize_latest_flight()