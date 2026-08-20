from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np

from tools import run_core_v3_vapor_holdup_thirty_second_trajectory as dd260


def test_dd260_continuity_reports_zero_for_repeated_reference_state():
    context = dd260.dd254._disturbed_problem()
    reference = context["reference"]

    class Endpoint:
        liquid_component_inventory_lbmol = reference.liquid_component_inventory_lbmol
        vapor_component_inventory_lbmol = reference.vapor_component_inventory_lbmol
        temperature_F = reference.temperature_F
        pressure_psia = reference.pressure_psia
        hydraulic_liquid_flow_lbmolph = reference.hydraulic_liquid_flow_lbmolph
        vapor_flow_lbmolph = reference.vapor_flow_lbmolph
        condenser_duty_BTUph = reference.condenser_duty_BTUph

    class Evaluation:
        endpoint = Endpoint()

    assert dd260._continuity(reference, [Evaluation()]) == {
        "temperature_F": 0.0,
        "pressure_psia": 0.0,
        "composition": 0.0,
        "flow_relative": 0.0,
        "phase_inventory_relative": 0.0,
        "duty_relative": 0.0,
    }


def test_dd260_refinement_comparison_detects_matching_endpoints():
    context = dd260.dd254._disturbed_problem()
    reference = context["reference"]
    endpoint = SimpleNamespace(
        liquid_component_inventory_lbmol=reference.liquid_component_inventory_lbmol,
        vapor_component_inventory_lbmol=reference.vapor_component_inventory_lbmol,
        temperature_F=reference.temperature_F,
        pressure_psia=reference.pressure_psia,
        hydraulic_liquid_flow_lbmolph=reference.hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=reference.vapor_flow_lbmolph,
        phase_transfer_lbmolph=reference.phase_transfer_lbmolph,
        condenser_duty_BTUph=reference.condenser_duty_BTUph,
    )
    evaluation = SimpleNamespace(endpoint=endpoint)
    comparison = dd260._refinement_comparison(
        evaluation,
        evaluation,
        reference.phase_transfer_scale_lbmolph,
    )

    assert all(value == 0.0 for value in comparison.values())


def test_dd260_saved_contract_freezes_thirty_seconds_and_local_refinement():
    saved = json.loads((dd260.ROOT / dd260.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["trajectory"] == {
        "nominal_step_sec": 0.25,
        "nominal_steps": 120,
        "nominal_duration_sec": 30.0,
        "refinement_start_sec": 29.75,
        "refined_step_sec": 0.125,
        "refined_steps": 2,
    }
    assert saved["method"]["fresh_jacobians_per_root"] == 1
    assert saved["reporting"]["incremental_recovery_after_each_nominal_endpoint"]
