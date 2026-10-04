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
| `Assets/1.unity` | **рабочая сцена**: новые модели `Gyrocopt` (дрон) и `Gruz` (груз). Активен рой `RSMAEnvironment 6` (6 дронов / 12 кг), рои на 5 и 4 дрона выключены | NetMQ-сервер поднимает сам менеджер роя (`startServer`, порт 5555) |
| `Assets/Scenes/SupremeFlat.unity` | старая сцена: префабы `Prefabs/Drones/Quadrocopter` + `Payload` | для сравнения |

## 4. Запуск

**Одной командой (сборка, Linux):**
```bash
./build.sh                                   # один раз и после изменений; редактор с проектом должен быть закрыт
./Builds/SwarmDelivery/SwarmDelivery.x86_64  # запуск
```
Для `build.sh` нужен модуль Unity Hub «Linux Build Support (Mono)». Собрать можно и из редактора:
меню **RSMA → Build SwarmDelivery (Linux)**.

**Из редактора:**
1. Откройте `Assets/1.unity` и нажмите **Play**.
2. В Console должно появиться `[RSMA Engine] Сцена успешно собрана: N дронов, груз M кг.`
3. Проверьте связь с Python (Unity в Play Mode):
   ```bash
   cd Tools/SwarmCheck
   pip install -r requirements.txt
   python swarm_check.py --drones 6                    # одна проверка
   python swarm_check.py --drones 6 --duration 60 --csv flight.csv   # запись 60 с
   ```
   `[OK] OK: Server is running` — связь есть. Таймаут — сцена не запущена или у менеджера роя выключен `startServer`.
4. Запустите Python-управление роем (отдельный код команды). Он подключается к `tcp://localhost:5555`
   и задаёт целевые точки дронов через топики `DroneTargetPose_<id>`.
5. После полета запустите файл визуализации из Python-кода. Он строит графики и считает характеристики полета.

Ориентир, как должно выглядеть: рой взлетает с площадки (синий круг), несёт груз на высоте ~12 м
к точке выгрузки (оранжевый круг), опускает груз, отцепляет тросы, возвращается и садится.
В HUD слева сверху отображаются этап, расстояние до точки, высота и скорость груза, натяжение тросов,
раскачка, путь, время и число рейсов.

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

**Менеджер роя** — компонент `RSMASwarmEnvironment` на сцене:

| Поле | Смысл | 1.unity (рой 1) |
|---|---|---|
| `numDrones` | число дронов (расставляются по кругу) | 6 |
| `payloadMass` | масса груза, кг | 12 |
| `radius` | радиус расстановки дронов, м | 3 |
| `cableLength` | свободная длина троса, м | 5 |
| `startPosition` | точка старта груза | (115, 1, 95.5) |
| `dronePrefab` / `payloadPrefab` | модели дрона и груза | `Gyrocopt` / `Gruz` |

Жёсткость (1000 Н/м), демпфирование (35 Н·с/м) и предел силы троса (250 Н) пока зашиты
в `RSMASwarmEnvironment.cs`.

**Дрон** — компонент `Quadrocopter` на префабе (`Assets/Models/Drone/Gyrocopt.prefab`):

| Поле | Смысл | Значение |
|---|---|---|
| `positionKp / Ki / Kd` | PID по позиции | 5 / 1 / 1.5 |
| `maxForce` | предел суммарной силы дрона, Н (это и есть «тяга») | 250 |
| `maxSpeed` | задумано как ограничение скорости, **в коде не используется** | 3 |
| масса | **жёстко 2.5 кг** в `Quadrocopter.Awake()`; значение в префабе игнорируется | 2.5 |

Шаг физики: `Fixed Timestep = 0.01` с (Project Settings → Time).

## 7. Кто что делает

- **Разработчики**: (1) компоненты на новых моделях, префабы дрона и груза; (2) менеджер роя на новой сцене;
  (3) проверка Python-части на новой сцене (`swarm_check.py` + управление роем).
- **Аналитики**: аналитика решения и сверка с ТЗ — `docs/ANALYTICS.md`.
