"""
Запуск миссии доставки груза роем в RSMA (сцена 1) с параметрами из командной строки.

Полет выполняет сама RSMA (встроенная миссия SwarmScriptedFlight): подъем, перелет на площадку,
выгрузка, возврат. Python только запускает сцену с нужными параметрами и показывает ход полета.

    python run.py                                   # параметры сцены по умолчанию
    python run.py --speed 6 --height 15             # быстрее и выше
    python run.py --delivery 60 30 --no-loop        # другая площадка, один рейс
    python run.py --payload-mass 15 --wind 5 --gust 2
    python run.py --drones 4 --fail-drone 2 --fail-time 40
    python run.py --config my_mission.json --speed 5
    python run.py --python-control                  # полетом управляет Python (Source/main.py)

Запускается собранное RSMA-приложение сцены 1 (Builds/SwarmDelivery) — редактор Unity не нужен.
Собрать его один раз (и после изменений в Unity-скриптах): python run.py --build
Если сборки нет — сцена запускается в редакторе Unity (или --editor). Если RSMA уже работает —
сцена 1 перезапускается с новыми параметрами. Все флаги: python run.py --help
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "Source"))

from RSMA.Client import RSMAClient  # noqa: E402
from RSMA.uDTP import is_published  # noqa: E402
from RSMA.uDTP.Topics import Float32, MissionStatus, Pose  # noqa: E402
from scene.launcher import DEFAULT_SCENE, UnityLaunchError, build_player, launch_unity  # noqa: E402

log = logging.getLogger("run")

# флаг -> (секция, поле Unity). Секции: delivery = SwarmDeliveryScene, environment = RSMASwarmEnvironment
FIELDS = {
    "speed": ("delivery", "cruiseSpeed"),
    "climb_speed": ("delivery", "climbSpeed"),
    "accel": ("delivery", "acceleration"),
    "climb_accel": ("delivery", "climbAcceleration"),
    "height": ("delivery", "cruiseHeight"),
    "drop_height": ("delivery", "dropHeight"),
    "unload_time": ("delivery", "unloadTime"),
    "hover_time": ("delivery", "hoverTime"),
    "loop": ("delivery", "loop"),
    "release": ("delivery", "releasePayload"),
    "kp": ("delivery", "positionKp"),
    "ki": ("delivery", "positionKi"),
    "kd": ("delivery", "positionKd"),
    "drones": ("environment", "numDrones"),
    "payload_mass": ("environment", "payloadMass"),
    "cable_length": ("environment", "cableLength"),
    "radius": ("environment", "radius"),
    "cable_stiffness": ("environment", "cableStiffness"),
    "wind": ("environment", "windSpeed"),
    "gust": ("environment", "gustAmplitude"),
    "fail_drone": ("environment", "failDroneId"),
    "fail_time": ("environment", "failTime"),
}


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Миссия доставки груза роем в RSMA (сцена 1) с параметрами",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)

    g = p.add_argument_group("маршрут и полет")
    g.add_argument("--speed", type=float, help="крейсерская скорость, м/с (по умолчанию 4)")
    g.add_argument("--height", type=float, help="высота перелета груза над землей, м (12)")
    g.add_argument("--climb-speed", type=float, help="скорость подъема/спуска, м/с (2.5)")
    g.add_argument("--accel", type=float, help="ускорение по горизонтали, м/с² (0.5)")
    g.add_argument("--climb-accel", type=float, help="ускорение по вертикали, м/с² (0.7)")
    g.add_argument("--base", type=float, nargs=2, metavar=("X", "Z"), help="база (координаты Unity), (115 85)")
    g.add_argument("--delivery", type=float, nargs=2, metavar=("X", "Z"), help="площадка доставки, (75 45)")
    g.add_argument("--drop-height", type=float, help="высота груза при выгрузке, м (0.55)")
    g.add_argument("--unload-time", type=float, help="время выгрузки, с (3)")
    g.add_argument("--hover-time", type=float, help="зависание перед посадкой, с (1.5)")
    g.add_argument("--loop", action=argparse.BooleanOptionalAction, default=None,
                   help="повторять рейсы (по умолчанию да); --no-loop — один рейс")
    g.add_argument("--release", action=argparse.BooleanOptionalAction, default=None,
                   help="отцеплять груз на площадке (по умолчанию да)")

    g = p.add_argument_group("рой и груз")
    g.add_argument("--drones", type=int, help="число дронов (6)")
    g.add_argument("--payload-mass", type=float, help="масса груза, кг (12)")
    g.add_argument("--cable-length", type=float, help="длина троса, м (2)")
    g.add_argument("--radius", type=float, help="радиус строя, м (1.414)")
    g.add_argument("--cable-stiffness", type=float, help="жесткость троса, Н/м (1000)")
    g.add_argument("--kp", type=float, help="ПИД дронов: Kp (40)")
    g.add_argument("--ki", type=float, help="ПИД дронов: Ki (12)")
    g.add_argument("--kd", type=float, help="ПИД дронов: Kd (14)")

    g = p.add_argument_group("внешние условия")
    g.add_argument("--wind", type=float, help="скорость ветра, м/с (0)")
    g.add_argument("--gust", type=float, help="амплитуда порывов, м/с (0)")
    g.add_argument("--wind-dir", type=float, nargs=2, metavar=("X", "Z"), help="направление ветра (0 1)")
    g.add_argument("--fail-drone", type=int, help="номер дрона, который откажет (0 — нет)")
    g.add_argument("--fail-time", type=float, help="время отказа, с (30)")

    g = p.add_argument_group("запуск")
    g.add_argument("--config", type=Path, help="JSON с параметрами {'delivery': {...}, 'environment': {...}}")
    g.add_argument("--print-config", action="store_true", help="только показать итоговые параметры")
    g.add_argument("--python-control", action="store_true",
                   help="полетом управляет Python-контроллер (Source/main.py), а не встроенная миссия")
    g.add_argument("--duration", type=float, default=None, help="сколько секунд показывать ход полета")
    g.add_argument("--no-monitor", action="store_true", help="запустить и сразу выйти")
    g.add_argument("--build", action="store_true",
                   help="собрать RSMA-приложение сцены 1 (один раз и после изменений в Unity), затем запустить")
    g.add_argument("--editor", action="store_true", help="запускать в редакторе Unity, а не собранное приложение")
    g.add_argument("--unity", help="путь к редактору Unity (иначе RSMA_UNITY или Unity Hub)")
    g.add_argument("--player", help="путь к собранному RSMA-приложению (по умолчанию Builds/SwarmDelivery)")
    g.add_argument("--host", default="localhost")
    g.add_argument("--port", type=int, default=5555)
    g.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def build_config(args: argparse.Namespace) -> dict:
    config: dict = {"delivery": {}, "environment": {}}
    if args.config:
        loaded = json.loads(args.config.read_text(encoding="utf-8"))
        for section in ("delivery", "environment"):
            config[section].update(loaded.get(section, {}))

    for flag, (section, field) in FIELDS.items():
        value = getattr(args, flag)
        if value is not None:
            config[section][field] = value
    if args.base:
        config["delivery"]["basePosition"] = {"x": args.base[0], "y": 0.0, "z": args.base[1]}
    if args.delivery:
        config["delivery"]["deliveryPosition"] = {"x": args.delivery[0], "y": 0.0, "z": args.delivery[1]}
    if args.wind_dir:
        config["environment"]["windDirection"] = {"x": args.wind_dir[0], "y": 0.0, "z": args.wind_dir[1]}
    return {k: v for k, v in config.items() if v}


def monitor(host: str, port: int, duration: float | None) -> None:
    """Печатает ход полета: этап, расстояние до площадки, высота груза, натяжение тросов."""
    start = time.monotonic()
    last_phase = None
    with RSMAClient(host=host, port=port, timeout=1000) as client:
        while duration is None or time.monotonic() - start < duration:
            requests = [("MissionStatus", MissionStatus), ("PayloadPose", Pose)]
            requests += [(f"CableForce_{i}", Float32) for i in range(1, 17)]
            status, payload, *forces = client.get_states(requests)
            if status is None and payload is None:
                log.warning("Нет связи со сценой (%s)", client.last_error)
            else:
                tension = sum(f.value for f in forces if is_published(f))
                phase = status.phase if is_published(status) else "—"
                line = (f"[{time.monotonic() - start:6.1f} с] {phase:<24} "
                        f"до площадки {status.distanceToFinish:6.1f} м  " if is_published(status) else
                        f"[{time.monotonic() - start:6.1f} с] {phase:<24} ")
                if is_published(payload):
                    p = payload.position
                    line += f"груз ({p.x:6.1f}, {p.y:5.1f}, {p.z:6.1f})  "
                line += f"Σ натяжение {tension:5.0f} Н"
                if phase != last_phase:
                    log.info("Этап: %s", phase)
                    last_phase = phase
                print(line, flush=True)
            time.sleep(1.0)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    config = build_config(args)
    print("Параметры миссии:", json.dumps(config, ensure_ascii=False) if config else "по умолчанию (из сцены)")
    if args.print_config:
        return 0

    try:
        if args.build:
            build_player(unity=args.unity)
        launch_unity(scene=DEFAULT_SCENE, host=args.host, port=args.port,
                     unity=args.unity if args.editor else None, player=args.player,
                     python_control=args.python_control, mission_config=config, prefer_player=not args.editor)
    except UnityLaunchError as e:
        print(f"Не удалось запустить сцену: {e}", file=sys.stderr)
        return 1

    if args.python_control:
        import main as controller  # Python/Source/main.py

        return controller.main(["--no-launch", "--host", args.host, "--port", str(args.port)])

    if args.no_monitor:
        print("Сцена запущена. Ход полета виден в RSMA (HUD слева сверху).")
        return 0
    print("Сцена запущена, полет выполняет RSMA. Ctrl+C — выйти (сцена продолжит работать).")
    try:
        monitor(args.host, args.port, args.duration)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
