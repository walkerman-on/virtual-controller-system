"""
Один шаг симуляции: чтение входов OPC по привязкам → ProcessModel → запись выходов.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from plant_registry import build_plant


class ModelSimulationRuntime:
    def __init__(self, config: dict[str, Any]) -> None:
        spec = config["model_plant"]
        self._plant_type = spec["type"]
        self._bindings = spec["bindings"]
        self.plant = build_plant(self._plant_type, config["model_parameters"])

    @property
    def bindings(self) -> dict[str, Any]:
        return self._bindings

    def run_step(
        self,
        get_tag: Callable[[str], Optional[float]],
        set_tag: Callable[[str, float], bool],
    ) -> Optional[dict[str, Any]]:
        """
        get_tag / set_tag — по имени тега OPC (как в config), не по node_id.
        """
        b_in = self._bindings["in"]
        b_out = self._bindings["out"]

        valve_opening = get_tag(b_in["valve_opening"])
        if valve_opening is None:
            valve_opening = 50.0
        if valve_opening < 0 or valve_opening > 100:
            valve_opening = max(0.0, min(float(valve_opening), 100.0))

        result = self.plant.calculate_step(valve_opening)
        if result is None:
            return None

        set_tag(b_out["liquid_level"], float(result["liquid_level"]))
        set_tag(b_out["outlet_flow"], float(result["outlet_flow"]))
        return result
