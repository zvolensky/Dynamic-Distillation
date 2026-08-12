from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_physical_modest_trajectory as dd178  # noqa: E402


def test_dd178_frozen_grid_has_forty_shared_times():
    coarse = dd178.dd177._step_count(dd178.DURATION_SEC, dd178.COARSE_DT_SEC)
    refined = dd178.dd177._step_count(dd178.DURATION_SEC, dd178.REFINED_DT_SEC)
    pairs = dd178.dd177._shared_step_pairs(coarse, refined)

    assert coarse == 40
    assert refined == 80
    assert pairs[0] == (1, 2)
    assert pairs[-1] == (40, 80)
    assert len(pairs) == 40


def test_dd178_accepts_the_frozen_dd177_authorization():
    result = json.loads((ROOT / dd178.DD177_RESULT).read_text(encoding="utf-8"))
    dd178._validate_source(result)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pass_gate", False, "accepted DD-177"),
        ("decision", "stop", "did not authorize"),
        ("completed_roots", 23, "root evidence changed"),
        ("controller_attempted", True, "controller boundary changed"),
    ],
)
def test_dd178_rejects_changed_dd177_authorization(field, value, message):
    result = json.loads((ROOT / dd178.DD177_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered[field] = value
    with pytest.raises(RuntimeError, match=message):
        dd178._validate_source(altered)


def test_dd178_compact_evidence_retains_endpoint_but_not_step_vectors():
    report = {
        "name": "path",
        "step_seconds": 0.25,
        "requested_steps": 1,
        "completed_steps": 1,
        "completed": True,
        "step_gates_pass": True,
        "total_inventory_history_lbmol": [1.0, 1.1],
        "total_inventory_strictly_increasing": True,
        "steps": [
            {
                "index": 1,
                "time_seconds": 0.25,
                "success": True,
                "nfev": 4,
                "njev": 4,
                "wall_clock_sec": 0.1,
                "residual_inf_norm": 1.0e-12,
                "jacobian_rank": 54,
                "jacobian_condition": 1.0e6,
                "component_rate_max_abs_lbmolph": 1.0,
                "energy_storage_rate_max_abs_BTUph": 2.0,
                "maximum_equilibrium_residual": 1.0e-14,
                "component_conservation_relative_error": 1.0e-14,
                "energy_conservation_relative_error": 1.0e-14,
                "component_kinematic_identity": 0.0,
                "energy_kinematic_identity": 0.0,
                "physical_pass": True,
                "gates": {"all": True},
                "inventory_lbmol": [[1.1]],
                "rate_coordinates": [[0.1]],
                "algebraic_coordinates": [0.2],
                "temperature_F": [100.0],
                "physical": {"all_finite": True},
            }
        ],
    }

    compact = dd178._compact_path(report)

    assert "inventory_lbmol" not in compact["steps"][0]
    assert compact["endpoint"]["inventory_lbmol"] == [[1.1]]
