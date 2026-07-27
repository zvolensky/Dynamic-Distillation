import copy
import json
from pathlib import Path

from dynamic_distillation.core_v3.dd112_physical_equivalence_adjudication_v1 import (
    adjudicate_dd112_physical_equivalence,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json"
CONTRACT = ROOT / "logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json"
LIMITS = {
    "objective_abs_difference": 1.0e-9,
    "inventory_scaled_difference": 1.0e-5,
    "liquid_composition_abs_difference": 1.0e-6,
    "lower_internal_energy_scaled_difference": 1.0e-6,
    "component_rate_scaled_difference": 1.0e-6,
    "internal_energy_rate_scaled_difference": 1.0e-6,
    "pressure_scaled_difference": 1.0e-6,
    "temperature_abs_difference_F": 1.0e-3,
    "vapor_composition_abs_difference": 1.0e-6,
    "bubble_composition_abs_difference": 1.0e-6,
    "liquid_flow_scaled_difference": 1.0e-6,
    "vapor_flow_scaled_difference": 1.0e-6,
    "distillate_scaled_difference": 1.0e-6,
    "bottoms_scaled_difference": 1.0e-6,
    "condenser_duty_scaled_difference": 1.0e-6,
}


def _evidence():
    return (
        json.loads(RESULT.read_text(encoding="utf-8")),
        json.loads(CONTRACT.read_text(encoding="utf-8")),
    )


def _audit(result, contract):
    return adjudicate_dd112_physical_equivalence(
        result,
        contract,
        limits=LIMITS,
        material_rate_scale_lbmolph=12584.8,
        energy_rate_scale_BTUph=55003568.3093669,
        pressure_scale_psia=10.0,
    )


def test_dd113_real_dd112_evidence_passes_physical_equivalence():
    result, contract = _evidence()
    audit = _audit(result, contract)

    assert audit.source_failed_gates == ("common_solution",)
    assert not audit.unexpected_source_failures
    assert all(audit.metric_gates.values())
    assert audit.compositions_physical
    assert audit.canonical_start == "dd094_storage_and_pressure_profile"
    assert audit.pass_gate


def test_dd113_rejects_material_inventory_disagreement():
    result, contract = _evidence()
    changed = copy.deepcopy(result)
    changed["starts"][1]["inventory_lbmol"][2][1] += 1.0

    audit = _audit(changed, contract)

    assert not audit.metric_gates["inventory_scaled_difference"]
    assert not audit.pass_gate


def test_dd113_rejects_vapor_composition_disagreement():
    result, contract = _evidence()
    changed = copy.deepcopy(result)
    changed["starts"][1]["final_coordinates"][43] += 0.01

    audit = _audit(changed, contract)

    assert not audit.metric_gates["vapor_composition_abs_difference"]
    assert not audit.pass_gate


def test_dd113_rejects_pressure_and_temperature_disagreement():
    result, contract = _evidence()
    changed = copy.deepcopy(result)
    changed["starts"][1]["pressure_psia"][2] += 0.1
    changed["starts"][1]["temperature_F"][2] += 0.1

    audit = _audit(changed, contract)

    assert not audit.metric_gates["pressure_scaled_difference"]
    assert not audit.metric_gates["temperature_abs_difference_F"]
    assert not audit.pass_gate


def test_dd113_cannot_override_an_unrelated_failed_gate():
    result, contract = _evidence()
    changed = copy.deepcopy(result)
    changed["gates"]["rank"] = False

    audit = _audit(changed, contract)

    assert audit.unexpected_source_failures == ("rank",)
    assert not audit.pass_gate


def test_dd113_requires_exactly_two_endpoints():
    result, contract = _evidence()
    changed = copy.deepcopy(result)
    changed["starts"].append(copy.deepcopy(changed["starts"][0]))

    try:
        _audit(changed, contract)
    except ValueError as exc:
        assert "exactly two" in str(exc)
    else:
        raise AssertionError("DD-113 accepted an extra endpoint")
