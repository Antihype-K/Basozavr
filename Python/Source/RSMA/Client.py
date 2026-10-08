import json
import logging
import threading
from typing import Any, TypeVar

import zmq

from RSMA.Serializer import RSMASerializer

T = TypeVar("T")

log = logging.getLogger("RSMA.Client")


class RSMAClient:
    """
    Client for the RSMA NetMQ server (Assets/Scripts/Apps/NetMQServer).

    Uses a REQ socket with the "Lazy Pirate" pattern: if the server does not
    answer within `timeout` ms, the socket is recreated, so one lost reply
    does not break all following requests.
    """

    def __init__(self, host: str = "localhost", port: int = 5555, timeout: int = 5000, retries: int = 1):
        self.endpoint = f"tcp://{host}:{port}"
        self.timeout = timeout
        self.retries = max(0, retries)
        self.last_error: str | None = None
        self.supports_batch: bool | None = None  # None — еще неизвестно

        self._lock = threading.Lock()
        self.context = zmq.Context()
        self.socket: zmq.Socket | None = None
        self._connect()

    # --- Транспорт ---

    def _connect(self) -> None:
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout)
        self.socket.connect(self.endpoint)

    def _reconnect(self) -> None:
        if self.socket is not None:
            self.socket.close(linger=0)
        self._connect()

    def _request(self, payload: str) -> str | None:
        """Sends one request and waits for the reply. Returns None on timeout."""
        with self._lock:
            if self.socket is None:
                raise RuntimeError("RSMAClient is closed")
            for attempt in range(self.retries + 1):
                try:
                    self.socket.send_string(payload)
                    if self.socket.poll(self.timeout, zmq.POLLIN):
                        self.last_error = None
                        return self.socket.recv_string()
                except zmq.ZMQError as e:
                    log.debug("ZMQ error on attempt %d: %s", attempt + 1, e)
                # REQ socket is now stuck waiting for a reply: recreate it
                self._reconnect()
                log.debug("No reply from %s (attempt %d/%d)", self.endpoint, attempt + 1, self.retries + 1)
            self.last_error = f"Timeout waiting for response from {self.endpoint}"
            return None

    # --- Простые команды ---

    def send_command(self, raw_command: str) -> str:
        """Sends text command to RSMA server (PrintMessage:..., RestartLevel, GetServerStatus)."""
        response = self._request(raw_command)
        if response is None:
            return "Error: Timeout waiting for response from Unity"
        return response

    def ping(self) -> bool:
        """True if the Unity server is reachable."""
        return self.send_command("GetServerStatus").startswith("OK")

    def print_message(self, message: str) -> str:
        """Prints message to the Unity console."""
        return self.send_command(f"PrintMessage:{message}")

    def restart_level(self) -> str:
        """Reloads the active Unity scene."""
        return self.send_command("RestartLevel")

    # --- uDTP ---

    @staticmethod
    def _topic_type_name(cls: type, topic_type: str | None) -> str:
        return topic_type or cls.__name__.split(".")[-1]

    def _publish_packet(self, topic_name: str, data_object: Any, topic_type: str | None) -> dict:
        return {
            "Action": "publish",
            "TopicName": topic_name,
            "TopicType": self._topic_type_name(type(data_object), topic_type),
            "Data": json.dumps(RSMASerializer.to_dict(data_object)),
        }

    def _get_packet(self, topic_name: str, target_class: type, topic_type: str | None) -> dict:
        return {
            "Action": "get",
            "TopicName": topic_name,
            "TopicType": self._topic_type_name(target_class, topic_type),
            "Data": "",
        }

    def _parse_publish(self, response_raw: str | None) -> dict:
        if response_raw is None:
            return {"status": "error", "message": "Timeout"}
        try:
            response = json.loads(response_raw)
        except json.JSONDecodeError:
            response = {"status": "error", "message": f"Raw response error: {response_raw}"}
        if response.get("status") != "ok":
            self.last_error = str(response.get("message", response))
        return response

    def _parse_get(self, response_raw: str | None, topic_name: str, target_class: type[T]) -> T | None:
        if response_raw is None:
            return None
        try:
            response = json.loads(response_raw)
            status = response.get("status") or response.get("Status")
            data_content = response.get("data") or response.get("Data")

            if status != "ok":
                self.last_error = str(response.get("message", response))
                return None
            if not data_content:
                return None

            parsed_json = json.loads(data_content)
            if parsed_json is None:
                return None
            return RSMASerializer.from_dict(target_class, parsed_json)
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError) as e:
            self.last_error = f"Bad response for '{topic_name}': {e}"
            log.warning(self.last_error)
            return None

    def publish(self, topic_name: str, data_object: Any, topic_type: str | None = None) -> dict:
        """
        Publishes data to topic via RSMA uDTP.
        Returns server response, e.g. {"status": "ok"} or {"status": "error", "message": ...}.
        """
        packet = self._publish_packet(topic_name, data_object, topic_type)
        return self._parse_publish(self._request(json.dumps(packet)))

    def get_state(self, topic_name: str, target_class: type[T], topic_type: str | None = None) -> T | None:
        """
        Gets latest topic state via RSMA uDTP.

        Returns None on transport or server errors (see `last_error`).
        Note: for a topic nobody published yet Unity returns a zero-filled
        struct, use `RSMA.uDTP.is_published()` to tell them apart.
        """
        packet = self._get_packet(topic_name, target_class, topic_type)
        return self._parse_get(self._request(json.dumps(packet)), topic_name, target_class)

    # --- Пакетные запросы (action "batch") ---

    def _batch(self, packets: list[dict]) -> list[str | None] | None:
        """
        Sends several broker packets in one request. Returns the raw response of each
        packet, [None, ...] on timeout, or None if the server does not support batches.
        """
        if not packets:
            return []
        if self.supports_batch is False:
            return None

        request = {"Action": "batch", "TopicName": "", "TopicType": "", "Data": json.dumps(packets)}
        response_raw = self._request(json.dumps(request))
        if response_raw is None:
            return [None] * len(packets)
        try:
            response = json.loads(response_raw)
            items = json.loads(response["data"]) if response.get("status") == "ok" else None
        except (json.JSONDecodeError, TypeError, KeyError):
            items = None
        if not isinstance(items, list) or len(items) != len(packets):
            # Старый сервер без batch: отвечает "Error: Unknown command ..."
            log.info("Server does not support batch requests, falling back to single requests")
            self.supports_batch = False
            return None
        self.supports_batch = True
        return items

    def get_states(self, requests: list[tuple[str, type]]) -> list[Any]:
        """
        Gets several topics in one round trip: get_states([("PayloadPose", Pose), ("CableForce_1", Float32)]).
        Each item is the same as get_state() would return.
        """
        packets = [self._get_packet(name, cls, None) for name, cls in requests]
        raws = self._batch(packets)
        if raws is None:
            return [self.get_state(name, cls) for name, cls in requests]
        return [self._parse_get(raw, name, cls) for raw, (name, cls) in zip(raws, requests, strict=True)]

    def publish_many(self, messages: list[tuple[str, Any]]) -> list[dict]:
        """Publishes several messages in one round trip: publish_many([("Topic", obj), ...])."""
        packets = [self._publish_packet(name, obj, None) for name, obj in messages]
        raws = self._batch(packets)
        if raws is None:
            return [self.publish(name, obj) for name, obj in messages]
        return [self._parse_publish(raw) for raw in raws]

    # --- Жизненный цикл ---

    def close(self) -> None:
        """Disconnects client."""
        with self._lock:
            if self.socket is not None:
                self.socket.close(linger=0)
                self.socket = None
            if not self.context.closed:
                self.context.term()

    def __enter__(self) -> "RSMAClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
