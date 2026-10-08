# Basozavr

Цифровой двойник доставки груза роем БПЛА на тросовых подвесах. Сделан на базе **RSMA**, пакета для
имитационного моделирования мобильных робототехнических комплексов в Unity.

* **Unity (RSMA)** моделирует физику: дроны (`Quadrocopter`, `PX4Quadrocopter`), упругие тросы
  (`RSMACable`), груз, датчики (лидар, камера, дальномер) и окружение.
* **Python** ([`Python/`](Python/README.md)) управляет роем: автомат состояний миссии,
  S-образная траектория, гашение раскачки груза, CSV-логи и дашборд.
* Связь между ними идет по **RSMA API (uDTP)**: топики с последним состоянием (`DataBroker`) и
  NetMQ-сервер (ZeroMQ, TCP 5555), см. `Assets/Scripts/uDTP` и `Assets/Scripts/Apps/NetMQServer`.

---

## Быстрый старт

1. Откройте проект в **Unity 6000.3.16f1** (Unity Hub → Add → папка репозитория).
2. Откройте сцену доставки (`Assets/1.unity` или `Assets/Scenes/SupremeFlat.unity`, в которых есть
   `RSMASwarmEnvironment`) и нажмите Play. NetMQ-сервер (`ServerApp`) поднимется на порту 5555.
3. Запустите контур управления на Python:

```bash
cd Python
python -m venv .venv && source .venv/bin/activate   # Windows: ./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
cd Source
python main.py
```

Без Unity контур можно запустить на встроенной физической модели сцены: `python main.py --sim --fast`.
Подробнее о параметрах, топиках и API клиента — в [Python/README.md](Python/README.md).

## Структура

| Путь | Что там |
|---|---|
| `Assets/Scripts/` | компоненты RSMA: механика, двигатели, датчики, микроконтроллеры, дроны, uDTP, приложения (NetMQ-сервер, планировщик миссий, менеджер объектов) |
| `Assets/Scenes/` | сцены: `SupremeFlat`, `SuspensionStand` (стенд подвески), `TestScenes/` |
| `Assets/Prefabs/` | префабы роботов, дронов, груза, колес |
| `Python/` | контур управления роем и Python-клиент RSMA API (тесты: `pytest`) |
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
