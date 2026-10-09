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

Нужны **Unity 6000.3.16f1** (через Unity Hub) и **Python 3.10+**. Сцену вручную открывать не нужно:
`main.py` и скрипты сами запускают Unity, открывают рабочую **сцену 1** (`Assets/1.unity`) в режиме
управления из Python и нажимают Play (если сцена уже запущена — просто подключаются).
Без Python сцена 1 выполняет встроенную миссию: откройте `Assets/1.unity` и нажмите Play (см. `docs/ONBOARDING.md`).

```bash
cd Python
python -m venv .venv && source .venv/bin/activate   # Windows: ./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
cd Source
python main.py          # запустит сцену и выполнит миссию доставки
```

Без Unity контур можно запустить на встроенной физической модели сцены: `python main.py --sim --fast`.
Подробнее о параметрах, топиках и API клиента — в [Python/README.md](Python/README.md).

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
