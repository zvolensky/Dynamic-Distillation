"""Structural specification for the first equilibrium-DAE v2 layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from dynamic_distillation.core_v2.reduced_topology_v1 import (
    ReducedColumnTopology,
    build_five_volume_topology,
)


PRESCRIBED_SECTION_VAPOR_MODE = "prescribed-section-rates"


@dataclass(frozen=True)
class ReducedColumnSpec:
    component_names: tuple[str, ...]
    topology: ReducedColumnTopology
    pressure_parameters: tuple[str, ...]
    vapor_flow_mode: str
    vapor_flow_parameters: tuple[str, ...]
    terminal_flow_parameters: tuple[str, ...]
    terminal_product_unknowns: tuple[str, ...]
    terminal_level_parameters: tuple[str, ...]
    duty_parameters: tuple[str, ...]
    feed_parameters: tuple[str, ...]
    hydraulic_parameters: tuple[str, ...]

    @property
    def external_parameters(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *self.pressure_parameters,
                    *self.vapor_flow_parameters,
                    *self.terminal_flow_parameters,
                    *self.terminal_level_parameters,
                    *self.duty_parameters,
                    *self.feed_parameters,
                    *self.hydraulic_parameters,
                )
            )
        )


def _validated_components(component_names: Sequence[str]) -> tuple[str, ...]:
    components = tuple(str(name).strip() for name in component_names)
    if len(components) < 2:
        raise ValueError("core_v2 requires at least two components")
    if any(not name for name in components):
        raise ValueError("component names must be nonempty")
    if len(set(components)) != len(components):
        raise ValueError("component names must be unique")
    return components


def build_reduced_column_spec(
    component_names: Sequence[str],
) -> ReducedColumnSpec:
    topology = build_five_volume_topology()
    components = _validated_components(component_names)
    volume_ids = topology.volume_ids
    hydraulic_nodes = tuple(
        stream.source_volume
        for stream in topology.internal_streams
        if stream.hydraulic_unknown
    )
    return ReducedColumnSpec(
        component_names=components,
        topology=topology,
        pressure_parameters=tuple(f"P[{node}]" for node in volume_ids),
        vapor_flow_mode=PRESCRIBED_SECTION_VAPOR_MODE,
        vapor_flow_parameters=("V_rectifying", "V_stripping"),
        terminal_flow_parameters=("R",),
        terminal_product_unknowns=("D", "B"),
        terminal_level_parameters=(
            "NL_target[reflux_drum]",
            "NL_target[combined_reboiler_sump]",
        ),
        duty_parameters=("Q_C", "Q_R"),
        feed_parameters=(
            *(f"F_component[{component}]" for component in components),
            "H_feed",
        ),
        hydraulic_parameters=tuple(
            f"francis_geometry[{node}]" for node in hydraulic_nodes
        ),
    )
