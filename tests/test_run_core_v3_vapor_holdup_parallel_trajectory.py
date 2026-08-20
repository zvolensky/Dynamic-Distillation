from __future__ import annotations

import json

import numpy as np

from tools import run_core_v3_vapor_holdup_parallel_trajectory as dd254


def test_dd254_reference_payload_round_trip_preserves_all_dynamic_fields():
    reference = dd254._disturbed_problem()["reference"]
    restored = dd254._reference_from_payload(dd254._reference_payload(reference))

    assert np.array_equal(
        restored.liquid_component_inventory_lbmol,
        reference.liquid_component_inventory_lbmol,
    )
    assert np.array_equal(
        restored.vapor_component_inventory_lbmol,
        reference.vapor_component_inventory_lbmol,
    )
    assert np.array_equal(restored.total_stored_energy_BTU, reference.total_stored_energy_BTU)
    assert np.array_equal(restored.pressure_psia, reference.pressure_psia)
    assert restored.condenser_duty_BTUph == reference.condenser_duty_BTUph


def test_dd254_saved_contract_freezes_persistent_parallel_trajectory():
    saved = json.loads((dd254.ROOT / dd254.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["trajectory"]["steps_per_path"] == 4
    assert saved["trajectory"]["worker_count"] == 8
    assert saved["trajectory"]["persistent_pool_count"] == 1
    assert saved["trajectory"]["color_count"] == 28
    assert saved["limits"]["parallel_trajectory_time_ratio"] == 0.75


def test_dd254_saved_result_rejects_only_parallel_speed():
    saved = json.loads((dd254.ROOT / dd254.RESULT).read_text(encoding="utf-8"))

    assert not saved["pass_gate"]
    assert saved["decision"] == "retain_serial_vapor_holdup_step_path"
    assert not saved["gates"]["parallel_speed"]
    assert not saved["gates"]["governed_speed"]
    assert all(
        passed
        for gate, passed in saved["gates"].items()
        if gate not in {"parallel_speed", "governed_speed"}
    )
    assert saved["comparison"]["serial_logical_work"] == 174480
    assert saved["comparison"]["parallel_logical_work"] == 174480
    assert max(saved["comparison"]["matrix_max_abs_differences"]) == 0.0
    assert max(saved["comparison"]["coordinate_max_abs_differences"]) == 0.0
