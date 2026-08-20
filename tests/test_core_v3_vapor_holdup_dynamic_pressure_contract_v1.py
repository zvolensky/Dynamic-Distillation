from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.provider_governed_registry_v1 import build_column_topology
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_contract_v1 import (
    CONDENSER_DUTY_PARAMETER,
    audit_vapor_holdup_dynamic_pressure_contract,
    build_vapor_holdup_dynamic_pressure_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"


def _contract(component_names: tuple[str, ...]):
    case = load_case_from_excel(str(WORKBOOK))
    column = build_column_spec_from_case(case)
    feed_stage = int(column.streams["Feed"].stage_1based)
    topology = build_column_topology(
        rectifying_volume_count=feed_stage - 2,
        stripping_volume_count=int(column.n_stages) - feed_stage - 1,
    )
    volume_geometry = build_column_vapor_geometry(column, case.specs, topology)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=gross_capacity_mapping(volume_geometry),
    )
    base = build_vapor_holdup_dae_contract(component_names, topology=vapor_topology)
    controlled = build_vapor_holdup_terminal_control_contract(
        base,
        geometry=terminal_geometry_from_specs(case.specs),
        controllers=level_controllers_from_specs(case.specs),
    )
    return build_vapor_holdup_dynamic_pressure_contract(controlled)


@pytest.mark.parametrize(
    "component_names",
    [("n-Propane", "n-Butane", "n-Pentane"), ("light", "heavy")],
)
def test_dynamic_pressure_contract_replaces_anchor_and_remains_full_rank(component_names):
    contract = _contract(component_names)
    audit = audit_vapor_holdup_dynamic_pressure_contract(contract)

    assert audit.pass_gate
    assert audit.solve_variable_count == audit.row_count == audit.structural_rank
    if len(component_names) == 3:
        assert audit.solve_variable_count == 262
    assert audit.pressure_anchor_count == 0
    assert audit.condenser_duty_specification_count == 1
    assert audit.top_pressure_coupled_outside_anchor
    assert audit.condenser_duty_coupled_to_energy_and_specification
    assert audit.fixed_top_pressure_removed
    assert audit.fixed_condenser_duty_present
    assert CONDENSER_DUTY_PARAMETER in contract.fixed_parameters
