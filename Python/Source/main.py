"""
Точка входа: контур управления роем при доставке груза.

    python main.py                     # подключение к RSMA (Unity) на localhost:5555
    python main.py --host 10.0.0.5     # RSMA на другой машине
    python main.py --sim               # без Unity: встроенная физическая модель сцены
    python main.py --sim --fast        # то же, без ожидания реального времени
"""

import argparse
import logging

import config
from control.swarm_controller import SwarmRSMAController


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSMA swarm delivery control loop")
    parser.add_argument("--host", default=config.RSMA_HOST, help="адрес RSMA NetMQ сервера")
    parser.add_argument("--port", type=int, default=config.RSMA_PORT, help="порт RSMA NetMQ сервера")
    parser.add_argument("--sim", action="store_true", help="работать со встроенной моделью вместо Unity")
    parser.add_argument("--fast", action="store_true", help="с --sim: не выдерживать реальное время")
    parser.add_argument("--max-steps", type=int, default=None, help="остановиться после N шагов")
    parser.add_argument("--no-csv", action="store_true", help="не писать CSV-лог полета")
    parser.add_argument("--payload-timeout", type=float, default=None,
                        help="сколько секунд ждать телеметрию груза (по умолчанию — бесконечно)")
    parser.add_argument("-v", "--verbose", action="store_true", help="подробный лог")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    config.RSMA_HOST, config.RSMA_PORT = args.host, args.port

    before_step = None
    if args.sim:
        from RSMA.Broker import InMemoryBroker, LocalClient
        from sim.swarm_sim import SwarmPhysicsSim

        broker = InMemoryBroker()
        controller = SwarmRSMAController(client=LocalClient(broker), csv_log=not args.no_csv)
        sim = SwarmPhysicsSim.around_payload(broker, payload_pos=[0.0, 0.0, 0.25], offsets=controller.offsets)
        before_step = sim.step
    else:
        controller = SwarmRSMAController(csv_log=not args.no_csv)
        if not controller.client.ping():
            logging.warning("RSMA не отвечает на %s:%d — жду запуска сцены...", args.host, args.port)

    realtime = not (args.sim and args.fast)
    phase = controller.run(realtime=realtime, max_steps=args.max_steps,
                           payload_timeout=args.payload_timeout, before_step=before_step)
    controller.client.close()
    return 0 if phase is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
