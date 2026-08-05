import copy
import json
from pathlib import Path

from dynamic_distillation.core_v3.dd132_physical_equivalence_adjudication_v1 import (
    adjudicate_dd132_physical_equivalence,
)


ROOT = Path(__file__).resolve().parents[1]
DD130_CONTRACT = ROOT / "logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_contract_20260805.json"
DD130_RESULT = ROOT / "logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_20260805.json"
DD132_RESULT = ROOT / "logs/dd132_core_v3_modified_newton_live_efficiency_20260805.json"
LIMITS = {
    "inventory_relative_difference": 2.0e-7,
    "liquid_holdup_relative_difference": 2.0e-7,
    "liquid_composition_abs_difference": 2.0e-7,
    "component_rate_scaled_difference": 2.0e-6,
    "top_internal_energy_relative_difference": 2.0e-7,
    "lower_internal_energy_relative_difference": 2.0e-7,
    "lower_energy_rate_scaled_difference": 2.0e-7,
    "controller_memory_abs_difference": 2.0e-7,
    "controller_rate_abs_difference_per_sec": 2.0e-7,
    "level_fraction_abs_difference": 2.0e-7,
    "temperature_abs_difference_F": 5.0e-5,
    "vapor_composition_abs_difference": 2.0e-7,
    "liquid_flow_relative_difference": 2.0e-7,
    "vapor_flow_relative_difference": 2.0e-7,
    "bubble_composition_abs_difference": 2.0e-7,
    "pressure_abs_difference_psia": 2.0e-6,
    "distillate_relative_difference": 1.0e-7,
    "bottoms_relative_difference": 1.0e-7,
    "condenser_duty_scaled_difference": 2.0e-7,
}


def _evidence():
    return tuple(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (DD130_RESULT, DD132_RESULT, DD130_CONTRACT)
    )


def _audit(dd130, dd132, contract):
    return adjudicate_dd132_physical_equivalence(
        dd130, dd132, contract, limits=LIMITS
    )


def test_dd133_real_evidence_passes_physical_equivalence():
    dd130, dd132, contract = _evidence()
    audit = _audit(dd130, dd132, contract)

    assert audit.dd130_failed_gates == ("calls",)
    assert audit.dd132_failed_gates == ("endpoint_reproduction",)
    assert all(all(item.values()) for item in audit.metric_gates.values())
    assert audit.decoded_states_physical
    assert audit.stored_products_match_coordinates
    assert audit.pass_gate


def test_dd133_rejects_physical_vapor_flow_disagreement():
    dd130, dd132, contract = _evidence()
    changed = copy.deepcopy(dd132)
    changed["outcomes"]["half2"]["final_coordinates"][37] += 1.0e-5

    audit = _audit(dd130, changed, contract)

    assert not audit.metric_gates["half2"]["vapor_flow_relative_difference"]
    assert not audit.pass_gate


def test_dd133_rejects_inventory_and_composition_disagreement():
    dd130, dd132, contract = _evidence()
    changed = copy.deepcopy(dd132)
    changed["outcomes"]["coarse"]["inventory_lbmol"][2][0] += 0.1

    audit = _audit(dd130, changed, contract)

    assert not audit.metric_gates["coarse"]["inventory_relative_difference"]
    assert not audit.metric_gates["coarse"]["liquid_composition_abs_difference"]
    assert not audit.pass_gate


def test_dd133_cannot_override_an_unrelated_dd132_gate():
    dd130, dd132, contract = _evidence()
    changed = copy.deepcopy(dd132)
    changed["gates"]["provider"] = False

    audit = _audit(dd130, changed, contract)

    assert audit.unexpected_dd132_failures == ("provider",)
    assert not audit.pass_gate


def test_dd133_rejects_stored_product_coordinate_disagreement():
    dd130, dd132, contract = _evidence()
    changed = copy.deepcopy(dd132)
    changed["outcomes"]["coarse"]["distillate_lbmolph"] += 1.0

    audit = _audit(dd130, changed, contract)

    assert not audit.stored_products_match_coordinates
    assert not audit.pass_gate


def test_dd133_requires_exactly_three_ordered_outcomes():
    dd130, dd132, contract = _evidence()
    changed = copy.deepcopy(dd132)
    changed["outcomes"].pop("half1")

    try:
        _audit(dd130, changed, contract)
    except ValueError as exc:
        assert "three ordered" in str(exc)
    else:
        raise AssertionError("DD-133 accepted an incomplete outcome ledger")
