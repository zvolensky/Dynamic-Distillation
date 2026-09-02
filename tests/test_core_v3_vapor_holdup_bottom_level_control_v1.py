from __future__ import annotations

from dynamic_distillation.core_v3.provider_governed_registry_v1 import DEFAULT_TOPOLOGY
from dynamic_distillation.core_v3.vapor_holdup_bottom_level_control_v1 import (
    BottomLevelControllerSpecification,
    audit_vapor_holdup_bottom_level_control_contract,
    bottom_level_control_bounds,
    bottom_level_control_initial_coordinates,
    build_vapor_holdup_bottom_level_control_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (
    VaporHoldupTerminalGeometry,
)


def _contract():
    base = build_vapor_holdup_dae_contract(
        ("light", "heavy"),
        topology=build_vapor_holdup_topology(
            column=DEFAULT_TOPOLOGY,
            vapor_volume_ft3={
                volume: 1000.0 for volume in DEFAULT_TOPOLOGY.volume_ids
            },
        ),
    )
    geometry = VaporHoldupTerminalGeometry(
        drum_diameter_ft=12.0,
        drum_tangent_length_ft=36.0,
        drum_head_shape="two_hemispherical",
        drum_gross_capacity_ft3=5000.0,
        sump_diameter_ft=20.0,
        sump_height_ft=6.0,
        sump_gross_capacity_ft3=1884.0,
        provenance="test geometry",
    )
    return build_vapor_holdup_bottom_level_control_contract(
        base,
        geometry=geometry,
        controller=BottomLevelControllerSpecification(
            setpoint_fraction=0.5,
            kc=24.0,
            ti_sec=365.0,
        ),
    )


def test_bottom_only_control_contract_is_square_and_full_structural_rank():
    contract = _contract()
    audit = audit_vapor_holdup_bottom_level_control_contract(contract)
    assert audit["pass_gate"]
    assert audit["dimension"] == len(contract.base.rows) + 2
    assert sum(row.block.startswith("bottom_level_controller") for row in contract.rows) == 2


def test_bumpless_predictor_keeps_zero_rate_and_nominal_bottoms_log_ratio():
    contract = _contract()
    point = bottom_level_control_initial_coordinates(
        contract,
        controller_rate_per_sec=0.0,
        timestep_sec=0.5,
    )
    lower, upper = bottom_level_control_bounds(contract)
    assert point.shape == (len(contract.rows),)
    assert point[-1] == 0.0
    assert (point > lower).all()
    assert (point < upper).all()
