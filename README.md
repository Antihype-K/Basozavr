# RSMA Public
RSMA - набор инструментов, методов и алгоритмов для разработки систем имитационного моделирования мобильных робототехнических комплексов. Пакет является расширением для среды разработки Unity.

---

## О проекте

Программный пакет содержит набор компонентов и интерфейсов для среды разработки Unity, позволяющий:

- Импортировать 3D-модели элементов конструкции робота;
- Моделировать работу механических компонентов робота с учетом физических законов;
- Разрабатывать и тестировать системы управления, включающие микроконтроллеры, устройства ввода/вывода и датчики;
- Воспроизводить разнообразные условия окружающей среды;
- Собирать данные о процессе моделирования и состоянии исследуемой системы.

 ## Дополнительные материалы для работы с RSMA

- [Документация к проекту](https://github.com/GrimDarkTech/RSMADocs)
- [Инструкция по установке](https://github.com/GrimDarkTech/RSMADocs/blob/main/Manual/ru/Installation/Installation.md)
# Basozavr

## БАСозавр: быстрый старт

- Сборка (сцена 1): Linux `./build.sh` → `./Builds/SwarmDelivery/SwarmDelivery.x86_64`; Windows `build.bat` → `Builds\SwarmDeliveryWin\SwarmDelivery.exe`
- [Как запустить решение](docs/ONBOARDING.md)
- [Аналитика и список на доработку](docs/ANALYTICS.md)
- [Гайд по тестированию](docs/TEST_GUIDE.md)
- [Разбор Python-контроллера команды (GitLab)](docs/PYTHON_CONTROLLER_REVIEW.md), код в `Python/`: `./Builds/SwarmDelivery/SwarmDelivery.x86_64 -python` и `python Python/main.py`
- Миссия доставки: `python Tools/SwarmControl/mission.py --dropoff X Z`; проверка требований на модели: `python Tools/SwarmModel/requirements_check.py`
- Проверка связи с Python: `Tools/SwarmCheck/swarm_check.py`, ступенчатый тест роя: `Tools/SwarmCheck/step_test.py`
