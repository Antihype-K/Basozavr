"""
In-process stand-ins for the Unity side, used for tests and offline runs.

* InMemoryBroker — the same semantics as RSMA.uDTP.DataBroker (C#): stores
  the latest message per (type, topic); `get` of an unpublished topic returns
  a zero-filled `default(T)`.
* LocalClient — drop-in replacement for RSMAClient that talks to a broker
  directly (no sockets), with the same JSON round trip as the real server.
"""

import copy
import json
import threading
from typing import Any, TypeVar

from RSMA.Serializer import RSMASerializer
from RSMA.uDTP.Topics import TOPIC_TYPES

T = TypeVar("T")


class UnknownTopicType(KeyError):
    pass


class InMemoryBroker:
    def __init__(self, topic_types: dict[str, type] | None = None):
        self.topic_types = dict(TOPIC_TYPES if topic_types is None else topic_types)
        self._states: dict[tuple[str, str], dict] = {}
        self._lock = threading.Lock()

    def _check_type(self, type_name: str) -> type:
        try:
            return self.topic_types[type_name]
        except KeyError:
            raise UnknownTopicType(type_name) from None

    def publish(self, type_name: str, topic_name: str, data: dict) -> None:
        self._check_type(type_name)
        with self._lock:
            self._states[(type_name, topic_name)] = copy.deepcopy(data)

    def get(self, type_name: str, topic_name: str) -> dict:
        cls = self._check_type(type_name)
        with self._lock:
            state = self._states.get((type_name, topic_name))
            if state is not None:
                return copy.deepcopy(state)
        return RSMASerializer.default_dict(cls)

    def topics(self) -> list[tuple[str, str]]:
        with self._lock:
            return sorted(self._states)

    # Convenience for simulators written in Python
    def publish_obj(self, topic_name: str, obj: Any) -> None:
        self.publish(type(obj).__name__, topic_name, RSMASerializer.to_dict(obj))

    def get_obj(self, topic_name: str, cls: type[T]) -> T:
        return RSMASerializer.from_dict(cls, self.get(cls.__name__, topic_name))


class LocalClient:
    """RSMAClient-compatible client bound to an InMemoryBroker."""

    def __init__(self, broker: InMemoryBroker | None = None):
        self.broker = broker or InMemoryBroker()
        self.last_error: str | None = None

    def send_command(self, raw_command: str) -> str:
        if raw_command.startswith("GetServerStatus"):
            return "OK: Server is running"
        return f"Error: Unknown command '{raw_command}'"

    def ping(self) -> bool:
        return True

    def publish(self, topic_name: str, data_object: Any, topic_type: str | None = None) -> dict:
        type_name = topic_type or type(data_object).__name__
        try:
            data = json.loads(json.dumps(RSMASerializer.to_dict(data_object)))
            self.broker.publish(type_name, topic_name, data)
        except UnknownTopicType:
            self.last_error = f"Type '{type_name}' not found"
            return {"status": "error", "message": self.last_error}
        return {"status": "ok"}

    def get_state(self, topic_name: str, target_class: type[T], topic_type: str | None = None) -> T | None:
        type_name = topic_type or target_class.__name__
        try:
            data = self.broker.get(type_name, topic_name)
        except UnknownTopicType:
            self.last_error = f"Type '{type_name}' not found"
            return None
        return RSMASerializer.from_dict(target_class, json.loads(json.dumps(data)))

    def get_states(self, requests: list[tuple[str, type]]) -> list[Any]:
        return [self.get_state(name, cls) for name, cls in requests]

    def publish_many(self, messages: list[tuple[str, Any]]) -> list[dict]:
        return [self.publish(name, obj) for name, obj in messages]

    def close(self) -> None:
        pass

    def __enter__(self) -> "LocalClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
