"""Unknown registry for the DD-077 reduced equilibrium-DAE core."""

from __future__ import annotations

from dataclasses import dataclass

from dynamic_distillation.core_v2.reduced_column_spec_v1 import ReducedColumnSpec


@dataclass(frozen=True)
class StateUnknown:
    name: str
    variable_kind: str
    block: str
    owner: str
    units: str
    closure_residual: str


def independent_components(spec: ReducedColumnSpec) -> tuple[str, ...]:
    return spec.component_names[:-1]


def composition_unknowns(
    spec: ReducedColumnSpec,
    *,
    phase: str,
    volume_id: str,
) -> tuple[str, ...]:
    return tuple(
        f"{phase}[{volume_id},{component}]"
        for component in independent_components(spec)
    )


def build_state_unknowns(spec: ReducedColumnSpec) -> tuple[StateUnknown, ...]:
    unknowns: list[StateUnknown] = []
    independent = independent_components(spec)

    for volume in spec.topology.control_volumes:
        node = volume.volume_id
        for component in spec.component_names:
            unknowns.append(
                StateUnknown(
                    name=f"N[{node},{component}]",
                    variable_kind="differential_state",
                    block="component_inventory",
                    owner=node,
                    units="lbmol",
                    closure_residual=f"component_reconstruction[{node},{component}]",
                )
            )
        unknowns.append(
            StateUnknown(
                name=f"U[{node}]",
                variable_kind="differential_state",
                block="internal_energy",
                owner=node,
                units="BTU",
                closure_residual=f"energy_reconstruction[{node}]",
            )
        )
        unknowns.append(
            StateUnknown(
                name=f"NL[{node}]",
                variable_kind="algebraic",
                block="liquid_amount",
                owner=node,
                units="lbmol",
                closure_residual=(
                    f"component_reconstruction[{node},{spec.component_names[-1]}]"
                ),
            )
        )
        for component in independent:
            unknowns.append(
                StateUnknown(
                    name=f"x[{node},{component}]",
                    variable_kind="algebraic",
                    block="liquid_composition",
                    owner=node,
                    units="mole_fraction",
                    closure_residual=f"component_reconstruction[{node},{component}]",
                )
            )
        unknowns.append(
            StateUnknown(
                name=f"T[{node}]",
                variable_kind="algebraic",
                block="temperature",
                owner=node,
                units="F",
                closure_residual=f"energy_reconstruction[{node}]",
            )
        )
        if volume.equilibrium_vapor_outlet:
            for component in independent:
                unknowns.append(
                    StateUnknown(
                        name=f"y[{node},{component}]",
                        variable_kind="algebraic",
                        block="vapor_composition",
                        owner=node,
                        units="mole_fraction",
                        closure_residual=f"phase_equilibrium[{node},{component}]",
                    )
                )

    for stream in spec.topology.internal_streams:
        if not stream.hydraulic_unknown:
            continue
        unknowns.append(
            StateUnknown(
                name=stream.flow_symbol,
                variable_kind="algebraic",
                block="liquid_flow",
                owner=stream.source_volume,
                units="lbmol_per_h",
                closure_residual=f"francis_hydraulics[{stream.source_volume}]",
            )
        )
    terminal_nodes = {
        stream.flow_symbol: stream.volume_id
        for stream in spec.topology.external_streams
        if stream.flow_symbol in spec.terminal_product_unknowns
    }
    for flow_symbol in spec.terminal_product_unknowns:
        node = terminal_nodes[flow_symbol]
        unknowns.append(
            StateUnknown(
                name=flow_symbol,
                variable_kind="algebraic",
                block="terminal_product_flow",
                owner=node,
                units="lbmol_per_h",
                closure_residual=(
                    f"component_balance[{node},{spec.component_names[-1]}]"
                ),
            )
        )
    return tuple(unknowns)
