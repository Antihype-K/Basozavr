from dataclasses import is_dataclass
from typing import Type, TypeVar, Any, Dict

from RSMA.Types.TypeRegistry import TYPE_REGISTRY

T = TypeVar('T')

class RSMASerializer:
    @classmethod
    def to_dict(cls, obj: Any) -> Any:
        """Рекурсивно сериализует dataclass-объекты в dict"""
        if is_dataclass(obj):
            return {f: cls.to_dict(getattr(obj, f)) for f in obj.__dataclass_fields__}
        elif isinstance(obj, (list, tuple)):
            return [cls.to_dict(x) for x in obj]
        elif isinstance(obj, dict):
            return {k: cls.to_dict(v) for k, v in obj.items()}
        return obj

    @classmethod
    def from_dict(cls, target_class: Type[T], data: Dict[str, Any]) -> T:
        """
        Рекурсивно восстанавливает типы данных из словаря, 
        опираясь на аннотации типов в dataclass.
        """
        if not is_dataclass(target_class):
            # Если это кастомный внешний класс со своей логикой
            if hasattr(target_class, 'from_dict'):
                return target_class.from_dict(data)
            obj = target_class()
            obj.__dict__.update(data)
            return obj

        init_kwargs = {}
        for field_name, field_def in target_class.__dataclass_fields__.items():
            field_data = data.get(field_name)
            field_type = field_def.type

            if isinstance(field_data, dict):
                # Проверяем, является ли поле другим датаклассом или зарегистрированным типом
                if is_dataclass(field_type):
                    init_kwargs[field_name] = cls.from_dict(field_type, field_data)
                elif field_type in cls.TYPE_REGISTRY.values():
                    init_kwargs[field_name] = cls.from_dict(field_type, field_data)
                else:
                    init_kwargs[field_name] = field_data
            else:
                # Если данные пришли пустыми, а у поля есть дефолтное значение
                if field_data is None and field_def.default is not None:
                    init_kwargs[field_name] = field_def.default
                else:
                    init_kwargs[field_name] = field_data

        return target_class(**init_kwargs)