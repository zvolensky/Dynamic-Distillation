from dataclasses import replace

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import SolveVariable
from dynamic_distillation.core_v3.pressure_consistent_initializer_contract_v1 import (
    InitializerConstraint,
    build_pressure_consistent_initializer_contract,
)
from dynamic_distillation.core_v3.pressure_initializer_readiness_v1 import (
    audit_pressure_initializer_readiness,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def _contract():
    return build_pressure_consistent_initializer_contract(COMPONENTS)


def test_dd107_stops_dd106_before_live_execution():
    audit = audit_pressure_initializer_readiness(_contract())

    assert audit.component_inventory_state_count == 15
    assert audit.component_inventory_rate_count == 15
    assert audit.algebraic_pressure_count == 4
    assert audit.energy_balance_count == 5
    assert not audit.live_numerical_contract_ready
    assert audit.decision == "stop_dd106_before_live_execution"


def test_dd107_detects_discrete_storage_without_continuous_energy_coordinates():
    audit = audit_pressure_initializer_readiness(_contract())

    assert audit.exact_discrete_storage_declared
    assert audit.independent_energy_state_count == 0
    assert audit.energy_rate_variable_count == 0
    assert audit.pressure_rate_variable_count == 0
    assert not audit.continuous_pressure_aware_energy_rate_defined


def test_dd107_confirms_nonzero_rates_are_selected_not_fixed_zero():
    audit = audit_pressure_initializer_readiness(_contract())

    assert audit.objective_permits_nonzero_inventory_rates
    assert not audit.nonzero_rates_fixed_by_constraint


def test_dd107_prohibits_reusing_fixed_pressure_storage_gradient():
    audit = audit_pressure_initializer_readiness(_contract())

    assert audit.timestep_prohibited
    assert not audit.fixed_pressure_gradient_reuse_permitted


def test_dd107_would_recognize_explicit_energy_state_and_rate_ownership():
    contract = _contract()
    states = contract.state_variables + tuple(
        SolveVariable(f"U[{volume}]", "internal_energy", volume)
        for volume in VOLUME_IDS
    )
    derivatives = contract.derivative_variables + tuple(
        SolveVariable(f"dU[{volume}]/dt", "internal_energy_rate", volume)
        for volume in VOLUME_IDS
    )
    audit = audit_pressure_initializer_readiness(
        replace(contract, state_variables=states, derivative_variables=derivatives)
    )

    assert audit.continuous_pressure_aware_energy_rate_defined
    assert audit.live_numerical_contract_ready


def test_dd107_would_recognize_explicit_zero_rate_constraints():
    contract = _contract()
    zero_rows = tuple(
        InitializerConstraint(
            name=f"zero_inventory_rate[{index}]",
            block="zero_inventory_rate",
            owner=variable.owner,
            dependencies=(variable.name,),
        )
        for index, variable in enumerate(contract.derivative_variables)
    )
    audit = audit_pressure_initializer_readiness(
        replace(contract, constraints=contract.constraints + zero_rows)
    )

    assert audit.nonzero_rates_fixed_by_constraint
    assert not audit.objective_permits_nonzero_inventory_rates
    assert audit.live_numerical_contract_ready
