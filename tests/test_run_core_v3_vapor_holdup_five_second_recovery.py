from __future__ import annotations

import json

import numpy as np

from tools import run_core_v3_vapor_holdup_five_second_recovery as dd259


def test_json_native_converts_nested_numpy_scalars_and_arrays():
    payload = {
        "gate": np.bool_(True),
        "value": np.float64(2.5),
        "count": np.int64(3),
        "nested": [np.asarray([1.0, 2.0])],
    }

    native = dd259.json_native(payload)
    encoded = json.dumps(native, allow_nan=False)

    assert json.loads(encoded) == {
        "gate": True,
        "value": 2.5,
        "count": 3,
        "nested": [[1.0, 2.0]],
    }


def test_reporting_preflight_exercises_the_previous_numpy_bool_failure():
    assert dd259._reporting_preflight() == {
        "json_native": True,
        "atomic_json": True,
        "atomic_npz": True,
        "complete_stage_profile": True,
    }


def test_dd259_saved_contract_uses_physical_duty_replay_and_recovery():
    saved = json.loads((dd259.ROOT / dd259.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["authorization"]["source"].startswith("explicit user authorization")
    assert saved["method"]["fresh_jacobians_per_root"] == 1
    assert saved["first_second_reference"]["non_duty_coordinate_absolute_difference"] == 1.0e-9
    assert saved["first_second_reference"]["condenser_duty_relative_difference"] == 1.0e-8
    assert saved["reporting"]["incremental_recovery_after_each_endpoint"]


def test_dd259_saved_result_passes_all_science_and_recovery_gates():
    saved = json.loads((dd259.ROOT / dd259.RESULT).read_text(encoding="utf-8"))
    recovery = json.loads((dd259.ROOT / dd259.RECOVERY).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert all(saved["gates"].values())
    assert saved["decision"] == (
        "accept_modified_newton_vapor_holdup_dynamics_through_five_seconds"
    )
    assert len(saved["endpoints"]) == 20
    assert len(saved["final_stage_profile"]) == 20
    assert saved["logical_provider_calls"] == 165480
    assert saved["wall_clock_sec"] < 60.0
    assert saved["response"]["component_inventory_identity_max_abs_lbmol"] < 1.0e-12
    assert recovery["status"] == "complete"
    assert recovery["completed_endpoint_count"] == 20
