# Basozavr

Цифровой двойник доставки груза роем БПЛА на тросовых подвесах. Сделан на базе **RSMA**, пакета для
имитационного моделирования мобильных робототехнических комплексов в Unity.

* **Unity (RSMA)** моделирует физику: дроны (`Quadrocopter`, `PX4Quadrocopter`), упругие тросы
  (`RSMACable`), груз, камера и окружение.
* **Python** ([`Python/`](Python/README.md)) управляет роем: автомат состояний миссии,
  S-образная траектория, гашение раскачки груза, CSV-логи и дашборд.
* Связь между ними идет по **RSMA API (uDTP)**: топики с последним состоянием (`DataBroker`) и
  NetMQ-сервер (ZeroMQ, TCP 5555), см. `Assets/Scripts/uDTP` и `Assets/Scripts/Apps/NetMQServer`.

---

## Быстрый старт

Полный гайд — [`ЗАПУСК.txt`](ЗАПУСК.txt). Все команды — с полным путем к `rsma.bat` / `rsma.sh`,
переходить в папку проекта не нужно; при первом запуске окружение Python создается само.

```bat
:: Windows — двойной щелчок по rsma.bat или из любой консоли
"C:\путь\к\BAS_RSMA\rsma.bat" --build              :: один раз: собрать RSMA (нужна Unity 6000.3.16f1)
"C:\путь\к\BAS_RSMA\rsma.bat"                      :: миссия доставки в RSMA
"C:\путь\к\BAS_RSMA\rsma.bat" --speed 6 --height 15
```

```bash
# Linux
~/путь/к/BAS_RSMA/rsma.sh --build                  # один раз: собрать RSMA
~/путь/к/BAS_RSMA/rsma.sh --build windows          # собрать под Windows + архив Builds/SwarmDelivery-Windows.zip
~/путь/к/BAS_RSMA/rsma.sh --speed 6 --height 15
```

Архив `SwarmDelivery-Windows.zip` (RSMA + Python-часть + `rsma.bat` + гайд) запускается на любом
компьютере с Windows и Python, Unity там не нужна: распаковать и запустить `rsma.bat`.

После успешной доставки (закончилась выгрузка груза) сохраняется отчет в `Python/logs/`
(`delivery_*.png` — путь груза сверху, высота, скорость, раскачка груза, натяжение тросов, итоги;
`delivery_*.csv` — данные) и открывается график. `--no-plot` — без графика, ход полета просто печатается в терминале.

`rsma` (это `Python/run.py`) запускает собранное RSMA-приложение (`Builds/SwarmDelivery`) напрямую: в нем только
сцена 1, старт за секунды, редактор Unity не нужен. Полет выполняет сама RSMA (встроенная миссия
`SwarmScriptedFlight`), Python только передает параметры и показывает ход полета в терминале.
Пересобирать (`--build`) нужно после изменений в Unity-скриптах — `run.py` предупредит.
Без сборки (или с `--editor`) сцена запускается в редакторе Unity; если RSMA уже работает —
сцена 1 перезапускается с новыми параметрами.

| Флаг | Что задает | По умолчанию |
|---|---|---|
| `--speed` / `--climb-speed` | крейсерская / вертикальная скорость, м/с | 4 / 2.5 |
| `--height` | высота перелета груза, м | 12 |
| `--accel` / `--climb-accel` | ускорение по горизонтали / вертикали, м/с² | 0.5 / 0.7 |
| `--base X Z` / `--delivery X Z` | база и площадка доставки (координаты Unity) | 115 85 / 75 45 |
| `--loop` / `--no-loop` | повторять рейсы | да |
| `--release` / `--no-release` | отцеплять груз на площадке | да |
| `--unload-time`, `--hover-time`, `--drop-height` | выгрузка, зависание, высота выгрузки | 3 с, 1.5 с, 0.55 м |
| `--drones`, `--payload-mass`, `--cable-length`, `--radius` | рой и груз | 6, 12 кг, 2 м, 1.414 м |
| `--kp --ki --kd`, `--cable-stiffness` | ПИД дронов, жесткость троса | 40/12/14, 1000 Н/м |
| `--wind`, `--gust`, `--wind-dir X Z` | ветер, порывы, направление | 0, 0, 0 1 |
| `--fail-drone N --fail-time T` | отказ дрона N в момент T | нет |
| `--config file.json` | параметры из файла (`{"delivery": {...}, "environment": {...}}`) | |
| `--python-control` | полетом управляет Python-контроллер (`Source/main.py`) | |

Параметры применяются поверх значений в сцене (`Assets/Scripts/UtilitiesForUnity/MissionConfig.cs`)
и сбрасываются после выхода из Play. Без Python: откройте `Assets/1.unity` и нажмите Play.
Подробнее о Python-части — в [Python/README.md](Python/README.md).

### Свои скрипты управления

Роем и грузом можно управлять короткими Python-скриптами. Скрипт сам запустит Unity,
откроет сцену 1 и нажмет Play, если сцена еще не запущена:

```python
from scene import connect

with connect() as sim:
    swarm = sim.swarm()
    swarm.lift(3.0)
    swarm.move_payload_by(10, 0, 5)
    swarm.lower()
    swarm.land()
```

Готовые примеры — в [`Python/Scripts`](Python/Scripts) (`python 03_deliver.py`,
`--offline` — без Unity). Из Unity их можно запускать командой `py <скрипт>` в терминале RSMA.
Подробности — в разделе «Управление роем из Python-скриптов» [Python/README.md](Python/README.md).

## Структура

| Путь | Что там |
|---|---|
| `Assets/Scripts/` | компоненты RSMA: механика, двигатели, датчики, микроконтроллеры, дроны, uDTP, приложения (NetMQ-сервер, планировщик миссий, менеджер объектов) |
| `Assets/1.unity` | **рабочая сцена 1**: доставка груза роем (`SwarmDeliveryScene`, HUD `SwarmLiveView`) |
| `Assets/Scenes/` | прочие сцены: `SupremeFlat` (старая), `SuspensionStand` (стенд подвески), `TestScenes/` |
| `docs/` | онбординг, тест-гайд, аналитика, обзор Python-контроллера |
| `Tools/SwarmModel`, `Tools/SwarmCheck`, `Tools/SwarmControl` | численная модель роя, проверки связи и миссии |
| `Assets/Prefabs/` | префабы роботов, дронов, груза, колес |
| `Python/` | контур управления роем, API `scene` и примеры скриптов (`Python/Scripts`), клиент RSMA API (тесты: `pytest`) |
| `Tools/NetMQHost/` | запуск C#-кода NetMQ-сервера вне Unity для проверки совместимости с Python-клиентом |
| `Features.md` | список модулей RSMA |

## Проверки

GitHub Actions (`.github/workflows/python.yml`) прогоняет `ruff` и `pytest` для Python, а также
interop-тесты: Python-клиент против C#-сервера из `Assets/Scripts/Apps/NetMQServer`.

## Материалы по RSMA

- [Документация RSMA](https://github.com/GrimDarkTech/RSMADocs)
- [Инструкция по установке](https://github.com/GrimDarkTech/RSMADocs/blob/main/Manual/ru/Installation/Installation.md)
- [Команды терминала](https://github.com/GrimDarkTech/RSMADocs/blob/main/Manual/en/Utilities/TerminalCommands.md)

Лицензия — [LICENSE](LICENSE).
