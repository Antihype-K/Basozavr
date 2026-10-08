# Swarm Delivery System — Python (RSMA API)

Контур управления роем БПЛА, переносящим груз на гибких тросах, для сцены Basozavr в RSMA (Unity).
Unity моделирует физику (6-DOF дроны, упругие тросы, груз), а Python — это «мозг» роя: он читает
телеметрию, ведет автомат состояний миссии, гасит раскачку груза и публикует целевые позиции дронов
через **RSMA API (uDTP поверх ZeroMQ/TCP)**.

Подробности алгоритмов: [Docs/Description.md](Docs/Description.md).
Перенесено из [rsma-swarm-delivery-system](https://gitlab.grimdark.ru/development/rsma-swarm-delivery-system)
(commit `3e1bcc5`), список изменений ниже.

---

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

### С Unity

1. Откройте проект в Unity и запустите сцену доставки. Сервер RSMA API (`ServerApp`, NetMQ)
   стартует на порту **5555**.
2. Запустите контур управления:

```bash
python main.py                   # localhost:5555
python main.py --host 10.0.0.5   # Unity на другой машине
```

Скрипт дождется первой телеметрии груза (`PayloadPose`) и выполнит миссию:
подъем → перелет → стабилизация → посадка груза → посадка дронов.
Лог полета пишется в `logs/flight_log_YYYYMMDD_HHMMSS.csv`.

Все параметры миссии (точка доставки, высота, скорости, коэффициенты anti-sway) задаются в
[`Source/config.py`](Source/config.py).

| Аргумент `main.py` | Назначение |
|---|---|
| `--host`, `--port` | адрес RSMA NetMQ сервера |
| `--sim` | встроенная физическая модель вместо Unity |
| `--fast` | с `--sim`: без ожидания реального времени |
| `--max-steps N` | остановиться через N шагов |
| `--no-csv` | не писать CSV-лог |
| `--payload-timeout S` | ждать телеметрию груза не дольше S секунд |
| `-v` | подробный лог |

`visualize.py [LOG.csv] [--save report.png]` строит дашборд по указанному или самому свежему логу.

---

## Топики uDTP

| Топик | Тип | Направление | Источник в Unity |
|---|---|---|---|
| `PayloadPose` | `Pose` | Unity → Python | `TransformPublisher` на грузе |
| `DronePose_i` | `Pose` | Unity → Python | `Quadrocopter.cs` |
| `CableForce_i` | `Float32` | Unity → Python | `RSMACable.cs` |
| `DroneTargetPose_i` | `Pose` | Python → Unity | читает `Quadrocopter.cs` |

Unity использует левую систему координат (Y — вверх), алгоритмы на Python — правую (Z — вверх).
Пересчет делают `utils/rsma_helpers.py` (`unity_to_py_v3`, `py_to_unity_v3`).

## RSMA API как библиотека

```python
from RSMA.Client import RSMAClient
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP import is_published
from RSMA.uDTP.Topics import Pose, RobotVelocity

with RSMAClient(host="localhost", port=5555, timeout=1000) as client:
    print(client.ping())                                     # True, если Unity отвечает
    client.publish("MaruzTargetVelocity", RobotVelocity(timestamp=1, linearVelocity=0.5))
    pose = client.get_state("MaruzPose", Pose)
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
├── tests/                    # pytest: типы, сериализация, клиент, алгоритмы, полная миссия
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
    │   └── SLAM/             # адаптер лидара для BreezySLAM (см. requirements-slam.txt)
    ├── control/
    │   ├── swarm_controller.py     # цикл управления (step / run)
    │   ├── flight_state_machine.py # LIFT → TRAJECTORY → HOVER → LAND → LAND_DRONES → FINISHED
    │   ├── trajectory.py           # S-образный профиль с ограничением скорости, ускорения и рывка
    │   ├── anti_sway.py            # гашение раскачки груза
    │   └── formation.py            # N-угольная формация
    ├── sim/swarm_sim.py      # физическая модель сцены (дроны, тросы, груз) для --sim и тестов
    └── utils/                # CSV/консольный логгер, пересчет систем координат
```

## Разработка

```bash
pip install -r requirements-dev.txt
pytest          # ~75 тестов, ~1 мин (включая полные миссии в модели)
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
  считается относительно номинальной геометрии. В модели при боковом ветре 15 Н среднее
  отклонение груза 0.079 м (без anti-sway 0.095 м, со старым алгоритмом 0.160 м), радиус формации
  сохраняется (1.31 м против 0.79 м у старого алгоритма).
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
