from dataclasses import replace

import numpy as np
import pytest

from dynamic_distillation.core_v3.handoff_balance_audit_v1 import (
    build_balance_term_ledger,
    ranked_component_term_changes,
    ranked_energy_term_changes,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    LiveProperties,
    _component_balances,
    _energy_balances,
)
from test_core_v3_conserved_nu_pressure_numerical_v1 import _nu_basis


def _fixture():
    _provider, spec, _reference, state, _contract, _inventory, _storage, _numerical, _point = _nu_basis()
    properties = LiveProperties(
        liquid_enthalpy_BTU_lbmol=np.asarray((-8000.0, -7000.0, -6000.0, -5000.0, -4000.0)),
        vapor_enthalpy_BTU_lbmol=np.asarray((1000.0, 2000.0, 3000.0, 4000.0, 5000.0)),
        liquid_density_lbmol_ft3=np.ones(5),
        francis_flow_lbmolph=np.ones(5),
        liquid_height_ft=np.ones(5),
        over_weir_head_ft=np.ones(5),
    )
    return spec, state, properties


def test_dd116_term_ledger_reproduces_governing_balances():
    spec, state, properties = _fixture()
    ledger = build_balance_term_ledger(spec, state, properties)

    assert np.allclose(ledger.component_net_lbmolph, _component_balances(spec, state))
    assert np.allclose(ledger.energy_net_BTUph, _energy_balances(spec, state, properties))


def test_dd116_internal_terms_telescope_to_external_component_and_energy_rates():
    spec, state, properties = _fixture()
    ledger = build_balance_term_ledger(spec, state, properties)
    component_external = (
        spec.feed_component_lbmolph
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )
    energy_external = (
        spec.feed_enthalpy_BTUph
        + spec.reboiler_duty_BTUph
        + state.condenser_duty_BTUph
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )

    assert np.allclose(np.sum(ledger.component_net_lbmolph, axis=0), component_external)
    assert np.isclose(np.sum(ledger.energy_net_BTUph), energy_external)


def test_dd116_change_rankings_reconcile_net_rate_changes():
    spec, state, properties = _fixture()
    first = build_balance_term_ledger(spec, state, properties)
    second_state = replace(
        state,
        vapor_flow_lbmolph=np.asarray(state.vapor_flow_lbmolph) * 1.01,
    )
    second = build_balance_term_ledger(spec, second_state, properties)
    bottom = VOLUME_IDS[-1]
    component = ranked_component_term_changes(
        first, second, volume=bottom, component_index=0
    )
    energy = ranked_energy_term_changes(first, second, volume=bottom)

    assert np.isclose(
        sum(value for _name, value in component),
        second.component_net_lbmolph[-1, 0] - first.component_net_lbmolph[-1, 0],
    )
    assert np.isclose(
        sum(value for _name, value in energy),
        second.energy_net_BTUph[-1] - first.energy_net_BTUph[-1],
    )
    assert component[0][0] == "vapor_out_to_stripping"
    assert energy[0][0] == "vapor_out_to_stripping"


def test_dd116_rejects_invalid_state_shape():
    spec, state, properties = _fixture()
    bad = replace(state, vapor_flow_lbmolph=np.ones(3))

    with pytest.raises(ValueError, match="shape"):
        build_balance_term_ledger(spec, bad, properties)
