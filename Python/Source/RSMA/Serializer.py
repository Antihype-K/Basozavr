import base64
import dataclasses
import types
import typing
from dataclasses import MISSING, is_dataclass
from functools import cache
from typing import Any, TypeVar

T = TypeVar("T")

# Values a C# struct field has after `default(T)`; used when JSON has no such key.
_ZERO_VALUES: dict[type, Any] = {int: 0, float: 0.0, str: "", bool: False, bytes: b""}


@cache
def _field_types(cls: type) -> dict[str, Any]:
    """Resolves dataclass field annotations (also when they are strings)."""
    return typing.get_type_hints(cls)


def _unwrap_optional(tp: Any) -> Any:
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


class RSMASerializer:
    """Converts uDTP dataclasses to JSON-ready dicts and back."""

    @classmethod
    def to_dict(cls, obj: Any) -> Any:
        """Рекурсивно сериализует dataclass-объекты в dict (bytes -> base64, как Newtonsoft)."""
        if is_dataclass(obj) and not isinstance(obj, type):
            return {f.name: cls.to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if isinstance(obj, (bytes, bytearray)):
            return base64.b64encode(bytes(obj)).decode("ascii")
        if isinstance(obj, (list, tuple)):
            return [cls.to_dict(x) for x in obj]
        if isinstance(obj, dict):
            return {k: cls.to_dict(v) for k, v in obj.items()}
        if hasattr(obj, "tolist"):  # numpy arrays and scalars
            return obj.tolist()
        return obj

    @classmethod
    def from_dict(cls, target_class: type[T], data: Any) -> T:
        """
        Рекурсивно восстанавливает типы данных из словаря,
        опираясь на аннотации типов в dataclass.
        Отсутствующие ключи получают значение по умолчанию поля.
        """
        return cls._convert(target_class, data)

    @classmethod
    def _convert(cls, tp: Any, value: Any) -> Any:
        tp = _unwrap_optional(tp)
        origin = typing.get_origin(tp)

        if value is None:
            return None

        if origin in (list, tuple):
            args = typing.get_args(tp)
            item_type = args[0] if args else Any
            return [cls._convert(item_type, v) for v in value]

        if tp is bytes:
            if isinstance(value, str):
                return base64.b64decode(value)
            return bytes(value)

        if isinstance(tp, type) and is_dataclass(tp):
            if not isinstance(value, dict):
                raise TypeError(f"Expected JSON object for {tp.__name__}, got {type(value).__name__}")
            if hasattr(tp, "from_dict") and tp.__dict__.get("from_dict") is not None:
                return tp.from_dict(value)
            return cls._build_dataclass(tp, value)

        if isinstance(tp, type) and hasattr(tp, "from_dict"):
            return tp.from_dict(value)

        if tp is float and isinstance(value, (int, float)):
            return float(value)
        if tp is int and isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    @classmethod
    def _build_dataclass(cls, tp: type, data: dict) -> Any:
        hints = _field_types(tp)
        kwargs = {}
        for f in dataclasses.fields(tp):
            if not f.init:
                continue
            if f.name in data and data[f.name] is not None:
                kwargs[f.name] = cls._convert(hints.get(f.name, Any), data[f.name])
            elif f.default is not MISSING or f.default_factory is not MISSING:
                continue  # let the dataclass apply its own default
            else:
                kwargs[f.name] = cls.zero_value(hints.get(f.name, Any))
        return tp(**kwargs)

    @classmethod
    def zero_value(cls, tp: Any) -> Any:
        """Value of `default(T)` in C# for the given Python annotation."""
        tp = _unwrap_optional(tp)
        if tp in _ZERO_VALUES:
            return _ZERO_VALUES[tp]
        if typing.get_origin(tp) in (list, tuple):
            return []
        if isinstance(tp, type) and is_dataclass(tp):
            return tp(**{f.name: cls.zero_value(_field_types(tp).get(f.name, Any))
                         for f in dataclasses.fields(tp) if f.init})
        return None

    @classmethod
    def default_dict(cls, target_class: type) -> dict:
        """
        JSON that the Unity NetMQ server returns for a topic nobody published yet:
        a C# `default(T)` struct (all zeros, Quaternion is (0,0,0,0), arrays omitted).
        """
        result = {}
        for f in dataclasses.fields(target_class):
            tp = _unwrap_optional(_field_types(target_class).get(f.name, Any))
            if typing.get_origin(tp) in (list, tuple) or tp is bytes:
                continue  # null arrays are dropped by NullValueHandling.Ignore
            if isinstance(tp, type) and is_dataclass(tp):
                result[f.name] = {sf.name: 0.0 for sf in dataclasses.fields(tp)}
            else:
                result[f.name] = _ZERO_VALUES.get(tp)
        return result
