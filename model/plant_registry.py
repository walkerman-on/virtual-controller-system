"""
Фабрика объекта процесса по полю model_plant.type.

Новая модель: зарегистрировать билдер через ``register_plant_type`` или добавить
в ``PLANT_BUILDERS`` (и реализовать класс с тем же контрактом, что ``ProcessModel``).
"""

from __future__ import annotations

from typing import Any, Callable

from process_model import ProcessModel

PlantBuilder = Callable[[dict[str, Any]], Any]

PLANT_BUILDERS: dict[str, PlantBuilder] = {
    "tank_process": lambda params: ProcessModel(params),
}


def register_plant_type(type_id: str, builder: PlantBuilder) -> None:
    """Подключить тип установки без правки ядра (вызывать при старте из своего модуля)."""
    if type_id in PLANT_BUILDERS:
        raise ValueError(f"Тип установки уже зарегистрирован: {type_id!r}")
    PLANT_BUILDERS[type_id] = builder


def list_plant_types() -> list[str]:
    return sorted(PLANT_BUILDERS.keys())


def build_plant(type_id: str, model_parameters: dict[str, Any]) -> Any:
    builder = PLANT_BUILDERS.get(type_id)
    if builder is None:
        raise KeyError(
            f"Неизвестный тип установки: {type_id!r}. Доступно: {list_plant_types()}"
        )
    return builder(model_parameters)
