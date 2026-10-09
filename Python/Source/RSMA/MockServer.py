"""
Python implementation of the Unity NetMQ server protocol
(Assets/Scripts/Apps/NetMQServer/Src/NetMqServer.cs).

Lets you develop and test Python clients without Unity:

    python -m RSMA.MockServer --port 5555
"""

import argparse
import json
import logging
import threading

import zmq

from RSMA.Broker import InMemoryBroker, UnknownTopicType

log = logging.getLogger("RSMA.MockServer")


class MockServer:
    def __init__(self, port: int = 5555, host: str = "*", broker: InMemoryBroker | None = None,
                 supports_batch: bool = True):
        """supports_batch=False emulates an older Unity build without the "batch" action."""
        self.endpoint = f"tcp://{host}:{port}"
        self.broker = broker or InMemoryBroker()
        self.supports_batch = supports_batch
        # Состояние "сцены" для GetSceneInfo / LoadScene (как NetMQServer в Unity)
        self.active_scene = "Assets/1.unity"
        self.external_control = True
        self.supports_scene_commands = True
        self.messages: list[str] = []  # PrintMessage log
        self.restart_count = 0

        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.ROUTER)
        self._socket.setsockopt(zmq.LINGER, 0)
        if port == 0:
            port = self._socket.bind_to_random_port(f"tcp://{host}")
        else:
            self._socket.bind(self.endpoint)
        self.port = port

        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    # --- Обработка команд (повторяет NetMQServer.ProcessCommand) ---

    def process_command(self, command: str) -> str:
        command = command.strip()
        if not command:
            return json.dumps({"status": "error", "message": "Empty payload"})

        if command.startswith("{") and command.endswith("}"):
            try:
                packet = json.loads(command)
            except json.JSONDecodeError:
                packet = None
            if isinstance(packet, dict):
                action = packet.get("Action") or packet.get("action")
                topic_type = packet.get("TopicType") or packet.get("topicType")
                if action == "batch" and self.supports_batch:
                    return self._process_batch(packet.get("Data") or packet.get("data"))
                if action and topic_type:
                    return self._process_broker_command(packet, action, topic_type)

        if command.startswith("PrintMessage:"):
            msg = command[len("PrintMessage:"):]
            self.messages.append(msg)
            log.info("Message: %s", msg)
            return "OK: Message printed"
        if command.startswith("RestartLevel"):
            self.restart_count += 1
            return "OK: Level restarting"
        if command.startswith("GetServerStatus"):
            return "OK: Server is running"
        if self.supports_scene_commands and command.startswith("GetSceneInfo"):
            return json.dumps({"status": "ok", "scene": self.active_scene, "externalControl": self.external_control})
        if self.supports_scene_commands and command.startswith("LoadScene:"):
            scene, _, flag = command[len("LoadScene:"):].partition("|")
            self.active_scene, self.external_control = scene.strip(), flag.strip() == "python"
            return f"OK: Loading {self.active_scene}"
        return f"Error: Unknown command '{command}'"

    def _process_batch(self, data: str | None) -> str:
        try:
            packets = json.loads(data or "[]")
        except json.JSONDecodeError as e:
            return json.dumps({"status": "error", "message": f"Bad batch: {e}"})
        responses = []
        for packet in packets if isinstance(packets, list) else []:
            action = isinstance(packet, dict) and packet.get("Action")
            topic_type = isinstance(packet, dict) and packet.get("TopicType")
            if not action or not topic_type:
                responses.append(json.dumps({"status": "error", "message": "Batch item must have Action and TopicType"}))
            else:
                responses.append(self._process_broker_command(packet, action, topic_type))
        return json.dumps({"status": "ok", "data": json.dumps(responses)})

    def _process_broker_command(self, packet: dict, action: str, topic_type: str) -> str:
        topic_name = packet.get("TopicName") or packet.get("topicName") or ""
        try:
            if action == "publish":
                data = json.loads(packet.get("Data") or packet.get("data") or "{}")
                self.broker.publish(topic_type, topic_name, data)
                return json.dumps({"status": "ok"})
            if action == "get":
                state = self.broker.get(topic_type, topic_name)
                return json.dumps({"status": "ok", "data": json.dumps(state)})
        except UnknownTopicType:
            return json.dumps({"status": "error", "message": f"Type '{topic_type}' not found"})
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"status": "error", "message": f"Bad data: {e}"})
        return json.dumps({"status": "error", "message": f"Unknown action '{action}'"})

    # --- Цикл сервера ---

    def serve_forever(self) -> None:
        self._running.set()
        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)
        while self._running.is_set():
            if not dict(poller.poll(100)):
                continue
            frames = self._socket.recv_multipart()
            if len(frames) < 3:
                continue
            identity, payload = frames[0], frames[-1]
            response = self.process_command(payload.decode("utf-8"))
            self._socket.send_multipart([identity, b"", response.encode("utf-8")])
        self._socket.close(linger=0)
        self._context.term()

    def start(self) -> "MockServer":
        self._thread = threading.Thread(target=self.serve_forever, name="RSMA-MockServer", daemon=True)
        self._thread.start()
        self._running.wait(1.0)
        return self

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> "MockServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="RSMA NetMQ server emulator (no Unity required)")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    server = MockServer(port=args.port)
    log.info("Listening on tcp://*:%d (Ctrl+C to stop)", server.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
