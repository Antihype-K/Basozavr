# Swarm Delivery System — Python (RSMA API)

Контур управления роем БПЛА, переносящим груз на гибких тросах, для сцены Basozavr в RSMA (Unity).
Unity моделирует физику (6-DOF дроны, упругие тросы, груз), а Python — это «мозг» роя: он читает
телеметрию, ведет автомат состояний миссии, гасит раскачку груза и публикует целевые позиции дронов
через **RSMA API (uDTP поверх ZeroMQ/TCP)**.

Подробности алгоритмов: [Docs/Description.md](Docs/Description.md).
Перенесено из [rsma-swarm-delivery-system](https://gitlab.grimdark.ru/development/rsma-swarm-delivery-system)
(commit `3e1bcc5`), список изменений ниже.

---

## Запуск миссии в RSMA с параметрами — `run.py`

Самый простой способ: полет выполняет сама RSMA (встроенная миссия сцены 1), а Python запускает
сцену и передает параметры флагами.

```bash
python run.py --build                           # один раз: собрать RSMA-приложение сцены 1
python run.py                                   # миссия с параметрами сцены
python run.py --speed 6 --height 15             # быстрее и выше
python run.py --delivery 60 30 --no-loop        # другая площадка, один рейс
python run.py --payload-mass 15 --wind 5 --gust 2
python run.py --drones 4 --fail-drone 2 --fail-time 40
python run.py --python-control                  # вместо встроенной миссии летит Python-контроллер
python run.py --help                            # все параметры
```

Как это работает:
* есть сборка (`Builds/SwarmDelivery`, `--build` или `./build.sh`) — `run.py` запускает это RSMA-приложение
  напрямую, без редактора; параметры передаются переменной окружения `RSMA_MISSION_CONFIG`;
* сборки нет (или `--editor`), Unity закрыта — `run.py` запускает редактор с проектом, параметры передаются переменной окружения
  `RSMA_MISSION_CONFIG`, `Assets/Editor/RSMALauncher.cs` открывает сцену 1 и нажимает Play;
* Unity открыта, но не в Play — `run.py` кладет запрос в `Temp/rsma_play_request.json`, редактор сам
  открывает сцену 1 с параметрами и нажимает Play (может спросить про сохранение открытой сцены);
* Unity уже в Play (любая сцена) — параметры передаются командой `SetMissionConfig`, сцена 1
  загружается командой `LoadScene`.

В сцене параметры применяет `MissionConfig.cs` поверх полей `SwarmDeliveryScene` и
`RSMASwarmEnvironment`; после выхода из Play они сбрасываются. Во время полета `run.py` печатает
этап миссии, расстояние до площадки, положение груза и суммарное натяжение тросов (Ctrl+C — выйти,
сцена продолжит работать).

## Быстрый старт

Нужен **Python 3.10+**.

```bash
cd Python
python -m venv .venv
# Windows (PowerShell):  ./.venv/Scripts/Activate.ps1
# Linux / macOS:         source .venv/bin/activate
pip install -r requirements.txt
cd Source
```

### Без Unity: встроенная модель сцены

```bash
python main.py --sim --fast      # миссия в ускоренном времени (~10 с)
python visualize.py              # дашборд последнего полета
```

### С Unity: сцена запускается сама

```bash
python main.py                   # запустит Unity, откроет сцену 1, нажмет Play и выполнит миссию
```

Если сцена уже запущена (сервер RSMA отвечает на порту 5555), скрипт просто подключится к ней.
Иначе он находит редактор Unity версии проекта (`ProjectSettings/ProjectVersion.txt`) в
Unity Hub, запускает его с проектом, открывает сцену 1 (`Assets/1.unity`) с ключом `-python` и входит
в Play (`Assets/Editor/RSMALauncher.cs`), ждет сервер и только потом начинает управлять.
С ключом `-python` `SwarmDeliveryScene` не запускает встроенную миссию: дроны держат позицию и ждут
команд Python, а HUD сцены (`SwarmLiveView`) показывает статус из топика `MissionStatus`.
Если редактора нет, но сцена собрана (`build.sh` / `build.bat`), запускается
`Builds/SwarmDelivery/SwarmDelivery.x86_64 -python`.

После подключения скрипт спрашивает у Unity, какая сцена открыта (`GetSceneInfo`). Если открыта
другая сцена или сцена 1 выполняет встроенную миссию (без `-python`), скрипт сам переключает ее
командой `LoadScene:Assets/1.unity|python` и ждет загрузки — в логе будет
«В Unity открыта ... — переключаю на Assets/1.unity».
Первый запуск на свежем клоне долгий: Unity импортирует ассеты (несколько минут).
После скрипта Unity остается открытой: следующие скрипты подключаются к ней сразу.

Если редактор стоит не в стандартной папке Unity Hub, укажите путь:
`export RSMA_UNITY=~/Unity/Hub/Editor/6000.3.16f1/Editor/Unity` (Windows:
`$env:RSMA_UNITY="C:\Program Files\Unity\Hub\Editor\6000.3.16f1\Editor\Unity.exe"`) или `--unity ПУТЬ`.
Если проект уже открыт в Unity, вторую копию Unity запустить нельзя — нажмите Play в открытой.

Миссия: подъем → перелет → стабилизация → посадка груза → посадка дронов.
Лог полета пишется в `logs/flight_log_YYYYMMDD_HHMMSS.csv`.
Все параметры миссии (точка доставки, высота, скорости, коэффициенты anti-sway) задаются в
[`Source/config.py`](Source/config.py).

| Аргумент `main.py` и скриптов | Назначение |
|---|---|
| `--no-launch` | не запускать Unity, только подключиться к уже запущенной сцене |
| `--scene ПУТЬ` | сцена для автозапуска (по умолчанию `Assets/1.unity`) |
| `--unity ПУТЬ` | редактор Unity (иначе `RSMA_UNITY` или Unity Hub) |
| `--player ПУТЬ` | запустить собранный плеер вместо редактора |
| `--close-unity` | закрыть запущенную скриптом Unity в конце |
| `--host`, `--port` | адрес сервера RSMA (на другой машине сцену запускают вручную) |
| `--sim` (`main.py`), `--offline` (скрипты) | встроенная модель вместо Unity |
| `--fast` | с `--sim`: без ожидания реального времени |
| `--max-steps N`, `--no-csv`, `--payload-timeout S`, `-v` | ограничение шагов, без CSV, таймаут телеметрии, подробный лог |

`visualize.py [LOG.csv] [--save report.png]` строит дашборд по указанному или самому свежему логу.

---

## Управление роем из Python-скриптов

Пакет `scene` — API для своих скриптов: рой с грузом и отдельные дроны.
Координаты как в Unity: **X — вправо, Y — вверх, Z — вперед**.

```python
import _rsma_path                     # в папке Python/Scripts: подключает Python/Source
from scene import connect

with connect() as sim:                # запустит сцену, если нужно; --offline — без Unity
    swarm = sim.swarm()               # все дроны и груз
    swarm.lift(3.0)                   # поднять груз на 3 м
    swarm.move_payload_by(10, 0, 5)   # перенести на 10 м по X и 5 м по Z
    swarm.lower()                     # опустить груз
    swarm.land()                      # посадить дронов

    print(swarm.payload_position, swarm.cable_forces())
    sim.drone(1).fly_to(0, 5, 10)     # отдельный дрон (тянет груз за трос!)
```

| Объект | Что умеет | Топики |
|---|---|---|
| `sim.swarm()` | `lift`, `move_payload_to`, `move_payload_by`, `set_payload_target`, `lower`, `land`, `payload_position`, `cable_forces` | все ниже |
| `sim.drone(i)` | `position`, `cable_force`, `set_target`, `fly_to`, `move_by`, `hover`, `land` | `DronePose_i` / `DroneTargetPose_i` |
| `sim` | `find_drones`, `payload_pose`, `cable_force`, `camera`, `sleep`, `wait_until`, `time`, `get`/`publish` любого топика, `print` в консоль Unity, `restart_level` | `PayloadPose`, `CableForce_i` |

`Swarm` запоминает формацию (смещения дронов от груза) в момент создания и задает положение
*груза*: дроны держат формацию над ним на высоте натянутых тросов.

**Примеры** в [`Scripts/`](Scripts):

```bash
cd Python/Scripts
python 01_hello.py               # дроны, груз и натяжение тросов
python 02_lift_and_hold.py       # поднять груз, подержать, опустить
python 03_deliver.py --dx 10 --dz 5   # перенести груз
python 04_camera_snapshot.py     # кадр с камеры RSMACamera
python -m scene                  # интерактивная консоль (из папки Python/Source)
```

**Запуск из Unity.** В терминале RSMA: `py` — список скриптов, `py 03_deliver.py` — запуск
(вывод идет в консоль Unity), `py_stop` — остановить. Интерпретатор задается переменной окружения
`RSMA_PYTHON` (по умолчанию `python` в Windows, `python3` в Linux/macOS), папка скриптов —
`RSMA_PYTHON_SCRIPTS` (по умолчанию `<проект>/Python/Scripts`).

**Офлайн-режим** (`--offline`, `Simulation.offline()`) — та же модель роя, тросов и груза, что для
`main.py --sim`. Время в нем виртуальное (`sim.sleep` продвигает модель), скрипты отлаживаются быстро.

## Топики uDTP

| Топик | Тип | Направление | Источник в Unity |
|---|---|---|---|
| `PayloadPose` | `Pose` | Unity → Python | `RSMASwarmEnvironment` (сцена 1) |
| `DronePose_i` | `Pose` | Unity → Python | `Quadrocopter.cs` |
| `CableForce_i` | `Float32` | Unity → Python | `RSMACable.cs` |
| `DroneTargetPose_i` | `Pose` | Python → Unity | читает `Quadrocopter.cs` |
| `MissionStatus` | `MissionStatus` | Python → Unity | HUD `SwarmLiveView` в сцене 1 |

Unity использует левую систему координат (Y — вверх), алгоритмы на Python — правую (Z — вверх).
Пересчет делают `utils/rsma_helpers.py` (`unity_to_py_v3`, `py_to_unity_v3`).

## RSMA API как библиотека

```python
from RSMA.Client import RSMAClient
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import Pose

with RSMAClient(host="localhost", port=5555, timeout=1000) as client:
    print(client.ping())                                     # True, если Unity отвечает
    client.publish("DroneTargetPose_1", Pose(position=Vector3(0, 5, 0), timestamp=1))
    pose = client.get_state("PayloadPose", Pose)
    if is_published(pose):                                   # не путать с пустой default-структурой
        print(pose.position, pose.rotation.to_yaw())
```

* В `RSMA.uDTP.Topics` есть Python-аналоги **всех** C#-топиков из `Assets/Scripts/uDTP/Topics`:
  `Pose`, `Float32`, `MotorInput`, `RobotVelocity`, `TrajectoryPoint`, `LaserScan128/256`,
  `CameraFramePacket`, `ActuatorInputs`, `ArmCommand`, `FlightModeCommand`, `RCChannelsInput`,
  `HILSensor`, `HILGPS`, `HILStateQuaternion`, `HILOpticalFlow`.
* Для топика, который в Unity еще никто не публиковал, сервер возвращает нулевую структуру
  `default(T)`. Отличить ее от данных можно через `is_published()` (у нее `timestamp == 0`).
* Если Unity не ответил за `timeout`, клиент возвращает `None` (`publish` — `{"status": "error"}`)
  и пересоздает сокет, так что следующие запросы работают дальше.
* `python -m RSMA.MockServer --port 5555` — эмулятор сервера Unity с тем же протоколом,
  для отладки своих клиентов без Unity.

---

## Структура

```text
Python/
├── requirements.txt          # зависимости (requirements-dev.txt — для тестов)
├── pyproject.toml            # настройки pytest и ruff
├── Docs/Description.md       # описание алгоритмов
├── Scripts/                  # примеры скриптов управления сценой (python 02_drone_square.py)
├── tests/                    # pytest: типы, сериализация, клиент, алгоритмы, миссия, scene API, interop
└── Source/
    ├── main.py               # точка входа: контур управления роем
    ├── config.py             # параметры миссии
    ├── visualize.py          # 4-панельный дашборд телеметрии
    ├── RSMA/                 # клиент RSMA API
    │   ├── Client.py         # RSMAClient (ZeroMQ REQ, автоматическое восстановление после таймаута)
    │   ├── Serializer.py     # dataclass <-> JSON в формате Newtonsoft
    │   ├── Broker.py         # InMemoryBroker и LocalClient (без сокетов, для симуляции и тестов)
    │   ├── MockServer.py     # эмулятор NetMQ-сервера Unity
    │   ├── Types/            # Vector3, Quaternion, Transform (как в Unity)
    │   ├── uDTP/Topics/      # топики uDTP
    ├── scene/                # API для скриптов: Simulation, Swarm, Drone, автозапуск Unity (launcher.py)
    ├── control/
    │   ├── swarm_controller.py     # цикл управления (step / run)
    │   ├── flight_state_machine.py # LIFT → TRAJECTORY → HOVER → LAND → LAND_DRONES → FINISHED
    │   ├── trajectory.py           # S-образный профиль с ограничением скорости, ускорения и рывка
    │   ├── anti_sway.py            # гашение раскачки груза
    │   └── formation.py            # N-угольная формация
    ├── sim/swarm_sim.py      # физическая модель сцены доставки (дроны, тросы, груз) для --sim и тестов
    ├── sim/scene_sim.py      # офлайн-сцена для скриптов (обертка над swarm_sim)
    └── utils/                # CSV/консольный логгер, пересчет систем координат
```

## Разработка

```bash
pip install -r requirements-dev.txt
pytest          # ~115 тестов, ~1.5 мин (включая полные миссии и примеры скриптов)
ruff check .
```

## Формат лога (`logs/flight_log_*.csv`)

* `timestamp` — Unix-время, мс; `step` — номер шага; `phase` — фаза автомата.
* `payload_x/y/z` — положение груза; `target_cmd_x/y/z` — уставка центра груза.
* `target_drone_z` — уставка высоты дронов; `dist_to_finish` — остаток пути по горизонтали.
* `avg_cable_tension` — среднее натяжение тросов, Н.
* `drone_i_x/y/z`, `cable_force_i` — положение `i`-го дрона и натяжение его троса.

---

## Изменения относительно исходного репозитория

**Исправленные ошибки**

* **Anti-sway стягивал формацию.** Штатный наклон троса (дрон смещен от груза на радиус формации,
  ~45°) принимался за раскачку, и каждый дрон смещался к грузу примерно на метр. Теперь раскачка
  считается относительно номинальной геометрии. В модели при ветре 15 Н среднее
  отклонение груза 0.070 м (без anti-sway 0.084 м, со старым алгоритмом 0.142 м), радиус формации
  сохраняется (1.30 м против 0.78 м у старого алгоритма).
* Anti-sway: на первом шаге производная давала скачок (предыдущий угол был 0), коррекция
  не ограничивалась, флаг `USE_ANTI_SWAY` игнорировался.
* **Клиент «зависал» после первого таймаута**: REQ-сокет ZeroMQ оставался в ожидании ответа,
  и все дальнейшие запросы падали. Добавлен паттерн Lazy Pirate.
* Пока Unity не опубликовал `PayloadPose`, сервер отдает нулевую структуру. Миссия начиналась
  из точки (0, 0, 0). Добавлен `is_published()`.
* `Serializer`: в отсутствующие поля подставлялся `dataclasses.MISSING`, обращение
  к несуществующему `cls.TYPE_REGISTRY`, не поддерживались `bytes` (кадры камеры).
* Автомат состояний: пороги 2.65 м / 0.55 м и высота 3.0 м были зашиты в код, хотя
  `CRUISE_ALTITUDE = 4.5`. HOVER мерился по системным часам. Миссия могла навсегда зависнуть
  в LAND, если груз высокий.
* Траектория не имела признака завершения и могла колебаться около цели. Заменена на
  точный S-образный профиль: без перелета, ограничения v/a/j выполняются на каждом шаге.
* `Quaternion.to_yaw()` давал неверный угол при наклоне корпуса (теперь совпадает с
  `eulerAngles.y` Unity). Опечатка `'Tranform'` в `TypeRegistry`.
* `requirements.txt` был в UTF-16, и `pip install -r` не работал на Linux/macOS.
* Деление на ноль в консольной телеметрии при совпадении старта и финиша.
* Резкий натяг тросов на первом шаге: уставка высоты дронов теперь растет с ограниченной скоростью.

**Новое**

* Топики для всех C#-структур uDTP, `Vector3`/`Quaternion` с операциями как в Unity.
* `MockServer`, `InMemoryBroker`/`LocalClient`, физическая модель сцены `sim/swarm_sim.py`
  и режим `main.py --sim`.
* Аргументы командной строки для `main.py` и `visualize.py` (в том числе `--save` для работы без окна).
* Тесты pytest и проверка ruff в CI (`.github/workflows/python.yml`).
