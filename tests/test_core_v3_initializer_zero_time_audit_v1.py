import copy
import json
from pathlib import Path

from dynamic_distillation.core_v3.initializer_zero_time_audit_v1 import (
    compare_saved_initializer_endpoint,
)


ROOT = Path(__file__).resolve().parents[1]
DD112 = ROOT / "logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json"
CONTRACT = ROOT / "logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json"
LIMITS = {
    "inventory_scaled_difference": 1.0e-8,
    "lower_internal_energy_scaled_difference": 1.0e-8,
    "component_rate_scaled_difference": 1.0e-8,
    "internal_energy_rate_scaled_difference": 1.0e-8,
    "pressure_scaled_difference": 1.0e-8,
    "temperature_abs_difference_F": 1.0e-6,
    "liquid_flow_scaled_difference": 1.0e-8,
    "vapor_flow_scaled_difference": 1.0e-8,
    "distillate_scaled_difference": 1.0e-8,
    "bottoms_scaled_difference": 1.0e-8,
    "condenser_duty_scaled_difference": 1.0e-8,
}


def _evidence():
    result = json.loads(DD112.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    saved = next(
        item
        for item in result["starts"]
        if item["name"] == "dd094_storage_and_pressure_profile"
    )
    return saved, contract


def _compare(saved, fresh, contract):
    return compare_saved_initializer_endpoint(
        saved,
        fresh,
        inventory_scale_lbmol=contract["inventory_reference_lbmol"],
        lower_energy_scale_BTU=contract["lower_internal_energy_scale_BTU"],
        material_rate_scale_lbmolph=12584.8,
        energy_rate_scale_BTUph=55003568.3093669,
        pressure_scale_psia=10.0,
        limits=LIMITS,
    )


def test_dd114_identical_saved_endpoint_passes():
    saved, contract = _evidence()
    comparison = _compare(saved, copy.deepcopy(saved), contract)

    assert all(value == 0.0 for value in comparison.metrics.values())
    assert all(comparison.gates.values())
    assert comparison.pass_gate


def test_dd114_rejects_inventory_or_rate_mismatch():
    saved, contract = _evidence()
    fresh = copy.deepcopy(saved)
    fresh["inventory_lbmol"][2][1] += 0.01
    fresh["component_rate_lbmolph"][2][1] += 1.0

    comparison = _compare(saved, fresh, contract)

    assert not comparison.gates["inventory_scaled_difference"]
    assert not comparison.gates["component_rate_scaled_difference"]
    assert not comparison.pass_gate


def test_dd114_rejects_pressure_or_temperature_mismatch():
    saved, contract = _evidence()
    fresh = copy.deepcopy(saved)
    fresh["pressure_psia"][2] += 0.01
    fresh["temperature_F"][2] += 0.01

    comparison = _compare(saved, fresh, contract)

    assert not comparison.gates["pressure_scaled_difference"]
    assert not comparison.gates["temperature_abs_difference_F"]
    assert not comparison.pass_gate


def test_dd114_rejects_flow_or_duty_mismatch():
    saved, contract = _evidence()
    fresh = copy.deepcopy(saved)
    fresh["vapor_flow_lbmolph"][1] += 1.0
    fresh["condenser_duty_BTUph"] += 1000.0

    comparison = _compare(saved, fresh, contract)

    assert not comparison.gates["vapor_flow_scaled_difference"]
    assert not comparison.gates["condenser_duty_scaled_difference"]
    assert not comparison.pass_gate
