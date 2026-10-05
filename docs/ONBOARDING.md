# БАСозавр — как запустить решение (к понедельнику)

Цель: каждый разработчик и аналитик умеет запустить сцену с роем, подключить Python
и поменять параметры роя/груза.

## 1. Что установить

| ПО | Версия | Зачем |
|---|---|---|
| Git | любая свежая | клонирование репозитория; **должен быть в PATH** — Unity по git-ссылкам ставит пакеты XCharts и NuGetForUnity |
| Unity Hub | последняя | установка редактора |
| Unity Editor | **6000.3.16f1** (ровно эта, см. `ProjectSettings/ProjectVersion.txt`) | сам проект |
| IDE | Visual Studio 2022 с нагрузкой «Разработка игр на Unity» (`.vsconfig` предложит её сам), либо Rider / VS Code | правка C#-скриптов |
| Python | 3.10+ | Python-часть (управление роем, визуализация полета) |
| Python-пакеты | `pip install pyzmq numpy matplotlib` | связь с Unity по NetMQ/ZeroMQ, графики |

NuGet-пакеты (NetMQ 4.0.4.2, Newtonsoft.Json 13.0.4 — список в `Assets/packages.config`)
NuGetForUnity восстанавливает сам при первом открытии проекта. Нужен интернет.

## 2. Получить проект

```bash
git clone https://github.com/antihype-k/basozavr.git
```

Репозиторий весит ~260 МБ. Unity Hub → **Add project from disk** → папка `basozavr`.
Первый импорт занимает 10–20 минут. Если Unity выдаёт ошибки компиляции про `NetMQ`/`Newtonsoft`,
выполните меню **NuGet → Restore Packages** и перезапустите редактор.

## 3. Сцены

| Сцена | Что там | Состояние |
|---|---|---|
| `Assets/1.unity` | **рабочая сцена «БАСозавр — доставка роем»**: объект `SwarmDelivery` (`SwarmDeliveryScene`) собирает рой (6 БПЛА, груз 12 кг, трос 2 м), `SwarmScriptedFlight` ведёт всю миссию внутри Unity: натяжение тросов → подъём → перенос → выгрузка → отцепка → возврат → посадка, с HUD и камерой. **Python не нужен**, достаточно Play | NetMQ-сервер для Python тоже поднимается (`startServer`, порт 5555) |
| `Assets/Scenes/SupremeFlat.unity` | старая сцена: префабы `Prefabs/Drones/Quadrocopter` + `Payload` | для сравнения |

## 4. Запуск

**Одной командой (сборка, Linux):**
```bash
./build.sh                                   # один раз и после изменений; редактор с проектом должен быть закрыт
./Builds/SwarmDelivery/SwarmDelivery.x86_64  # запуск
```
Для `build.sh` нужен модуль Unity Hub «Linux Build Support (Mono)». Собрать можно и из редактора:
меню **RSMA → Build SwarmDelivery (Linux)**.

**Windows (PowerShell или cmd, из корня проекта):**
```bat
build.bat
Builds\SwarmDeliveryWin\SwarmDelivery.exe
```
Либо из редактора: меню **RSMA → Build SwarmDelivery (Windows)**. Либо просто откройте `Assets/1.unity` в редакторе и нажмите Play.
Установка: Git (с «Add to PATH»), Unity Hub и Unity 6000.3.16f1 (Windows Build Support ставится по умолчанию), Python 3.10+ («Add Python to PATH»),
`pip install pyzmq numpy matplotlib`. Скрипты Python запускаются так же: `python Tools\SwarmCheck\swarm_check.py --drones 6`.

**Из редактора:**
1. Откройте `Assets/1.unity` и нажмите **Play**: рой сам выполнит всю миссию, в HUD слева сверху видны этап, расстояние до точки,
   высота и скорость груза, натяжение тросов, раскачка, путь, время и число рейсов.
2. В Console должно появиться `[RSMA Engine] Сцена успешно собрана: N дронов, груз M кг.`
3. Проверьте связь с Python (Unity в Play Mode, **необязательно**: нужно только для записи телеметрии):
   ```bash
   cd Tools/SwarmCheck
   pip install -r requirements.txt
   python swarm_check.py --drones 6                    # одна проверка
   python swarm_check.py --drones 6 --duration 60 --csv flight.csv   # запись 60 с
   ```
   `[OK] OK: Server is running` — связь есть. Таймаут — сцена не запущена или у менеджера роя выключен `startServer`.
4. **Python-контроллер команды** (папка `Python/`, перенесена из GitLab `rsma-swarm-delivery-system`): запустите сцену в режиме
   внешнего управления. В собранной игре это ключ `-python`, в редакторе включите `externalControl` у `SwarmDeliveryScene`:
   ```bash
   ./Builds/SwarmDelivery/SwarmDelivery.x86_64 -python    # Windows: Builds\SwarmDeliveryWin\SwarmDelivery.exe -python
   pip install -r Python/requirements.txt                 # один раз
   python Python/main.py                                  # миссия: подъём, перенос на оранжевую площадку, посадка груза и дронов
   python Python/visualize.py                             # графики последнего полёта (из logs/)
   ```
   **Визуализация в самой RSMA.** Пока работает Python, сцена показывает: панель «Python-контроллер» (фаза миссии, расстояние до
   финиша, прогресс маршрута, высота и скорость груза, раскачка, натяжение), живые графики раскачки груза, натяжения тросов
   (сумма / мин / макс) и высоты груза за последние 90 с, жёлтый след груза и бирюзовый шар-уставку, куда Python ведёт груз.
   Статус публикует Python в топик `MissionStatus` (`Python/control/swarm_controller.py`), остальное считает Unity по физике
   (`Assets/Scripts/UtilitiesForUnity/SwarmLiveView.cs`). `Python/visualize.py` остаётся для разбора CSV-логов после полёта.
   Встроенная миссия в этом режиме отключена, дроны держат позицию до первой команды Python. Параметры миссии — `Python/config.py`
   (`TARGET_OFFSET_X/Y` — смещение от базы до точки доставки, `CRUISE_ALTITUDE`, `V_MAX`, `K_SWAY/D_SWAY`).
   Подробности и найденные проблемы: `docs/PYTHON_CONTROLLER_REVIEW.md`.

   Другой Python-вариант, `mission.py` (простой контроллер из `Tools/SwarmControl`):
   ```bash
   python Tools/SwarmControl/mission.py --drones 6 --payload-mass 19.8 --dropoff <X> <Z> --log mission.csv
   ```
   Контроллер подключается к `tcp://localhost:5555` и задаёт цели дронов через `DroneTargetPose_<id>`.
   `<X> <Z>` — координаты оранжевой площадки выгрузки на сцене (Unity: объект площадки → Transform → Position).
   Без Unity логику этапов можно прогнать на имитаторе: `python Tools/SwarmControl/mock_unity.py` (только кинематика).
5. После полёта запустите файл визуализации из Python-кода (он строит графики и считает характеристики полёта).

Ориентир, как должно выглядеть: рой взлетает с площадки (синий круг), несёт груз на высоте ~12 м
к точке выгрузки (оранжевый круг), опускает груз, отцепляет тросы, возвращается и садится.

## 5. Протокол Unity ↔ Python

NetMQ `RouterSocket` на порту **5555** (`Assets/Scripts/Apps/NetMQServer/Src/NetMqServer.cs`).
Клиент: `zmq.REQ`, сообщение — JSON:

```json
{"Action": "get",     "TopicName": "DronePose_1",       "TopicType": "Pose",    "Data": ""}
{"Action": "publish", "TopicName": "DroneTargetPose_1", "TopicType": "Pose",
 "Data": "{\"position\":{\"x\":115,\"y\":12,\"z\":95},\"rotation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"timestamp\":0}"}
```

`Data` — это JSON, упакованный в строку. Координаты Unity: **Y — вверх**.

| Топик | Тип | Кто публикует | Содержимое |
|---|---|---|---|
| `DronePose_<id>` | Pose | Unity (`Quadrocopter`) | позиция и ориентация дрона |
| `DroneTargetPose_<id>` | Pose | Python | целевая точка дрона (нулевой вектор игнорируется) |
| `CableForce_<id>` | Float32 | Unity (`RSMACable`) | натяжение троса, Н |

Текстовые команды: `GetServerStatus`, `RestartLevel`, `PrintMessage:<текст>`.

## 6. Какие параметры настраивать

**Миссия сцены 1** — компонент `SwarmDeliveryScene` на объекте `SwarmDelivery`:

| Поле | Смысл | Значение |
|---|---|---|
| `basePosition` / `deliveryPosition` | база и точка доставки (XZ, высота по рельефу) | (115, 85) / (75, 45), плечо 56,6 м |
| `cruiseHeight` | высота груза при переносе, м | 12 |
| `cruiseSpeed` / `climbSpeed` | скорость переноса / подъёма, м/с | 4 / 2,5 |
| `climbAcceleration` | ограничение вертикального ускорения, м/с²: мягкий подъём и посадка груза | **0,7** (раньше без ограничения) |
| `acceleration` | ограничение ускорения цели, м/с²: главное средство против раскачки | **0,5** (было 1,0) |
| `swingDamping` | сдвиг строя по скорости груза: на модели **увеличивает** раскачку | **0** (было 0,15) |
| `positionKp / Ki / Kd` | ПИД дронов под нагрузкой (переопределяет префаб) | 40 / 12 / 14 |
| `unloadTime`, `hoverTime`, `loop` | выдержки и зацикливание миссии | 3 с, 1,5 с, вкл. |

**Менеджер роя** — компонент `RSMASwarmEnvironment` на сцене:

| Поле | Смысл | 1.unity (рой 1) |
|---|---|---|
| `numDrones` | число дронов (расставляются по кругу) | 6 |
| `payloadMass` | масса груза, кг | 12 |
| `radius` | радиус расстановки дронов, м | 1,414 |
| `cableLength` | свободная длина троса, м | 2 |
| `startPosition` | точка старта груза (задаётся `SwarmDeliveryScene`) | база (115, 85) |
| `dronePrefab` / `payloadPrefab` | модели дрона и груза | `Quadrocopter` / `Payload` |

Там же: параметры троса (`cableStiffness` 1000 Н/м, `cableDamping` 35 Н·с/м, `cableMaxForce` 250 Н),
ветер (`windSpeed`, `gustAmplitude`, `windDirection`), отказ дрона (`failDroneId`, `failTime`),
сервер для Python (`startServer`, `serverPort`).

**Дрон** — компонент `Quadrocopter`. Сцена 1 использует префаб `Assets/Prefabs/Drones/Quadrocopter.prefab` (тяга 250 Н, ПИД
`SwarmDeliveryScene` переопределяет на 40 / 12 / 14). Префаб `Assets/Models/Drone/Gyrocopt.prefab` (новая модель) настроен
под эталонное решение из аналитики:

| Поле | Смысл | `Gyrocopt` |
|---|---|---|
| `positionKp / Ki / Kd` | PID по позиции (подобрано перебором на модели для троса 5 м, радиуса 3 м) | 10 / 2 / 12 |
| `maxForce` | предел силы дрона, Н (тяга): P₁ = 3,3 кг + запас 25 % | 71 |
| `maxIntegralForce` | ограничение интегральной составляющей, Н | 250 |
| `smoothTarget` | вести цель с ограничением скорости и ускорения (меньше раскачка) | выкл. |
| `maxSpeed` / `maxAcceleration` | ограничения для `smoothTarget`, м/с и м/с² | 3 / 0,3 |
| `droneMass`, `linearDrag`, `angularDrag` | масса и сопротивление | 2,5 / 0,8 / 3 |
| `isFailed` | имитация отказа дрона | выкл. |

Шаг физики: `Fixed Timestep = 0.01` с (Project Settings → Time).

## 7. Проверка требований на модели

```bash
pip install numpy
python Tools/SwarmModel/requirements_check.py                      # эталонное решение: трос 5 м, радиус 3 м, тяга 71 Н
python Tools/SwarmModel/requirements_check.py --preset scene1 --fmax 250   # геометрия и ПИД сцены 1
python Tools/SwarmModel/scene1_swing.py                            # раскачка на сцене 1: калибровка по видео и перебор параметров
python Tools/SwarmModel/scene1_mission.py                          # то же по этапам миссии: раскачка, натяжение, скорость касания груза
```
За ~30 с прогоняет линейность 400/600 %, предел груза, ветер и отказ дрона на модели с формулами из Unity.

## 8. Кто что делает

- **Разработчики**: (1) компоненты на новых моделях, префабы дрона и груза; (2) менеджер роя на новой сцене;
  (3) проверка Python-части на новой сцене (`swarm_check.py` + управление роем).
- **Аналитики**: аналитика решения и сверка с ТЗ — `docs/ANALYTICS.md`.
