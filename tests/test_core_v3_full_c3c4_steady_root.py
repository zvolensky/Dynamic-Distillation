import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_full_c3c4_steady_root as dd223


def _contract():
    return json.loads((ROOT / dd223.CONTRACT).read_text(encoding="utf-8"))


def test_dd223_contract_freezes_two_independent_160_coordinate_starts():
    contract = _contract()

    assert tuple(contract["starts"]) == (
        "source_mapped_seed",
        "independent_smooth_topology_seed",
    )
    assert all(len(point) == 160 for point in contract["starts"].values())
    assert contract["start_separation_inf"] > 0.1
    assert contract["independent_start_metadata"]["full_residual_used"] is False
    assert contract["independent_start_metadata"]["continuation_used"] is False


def test_dd223_contract_uses_validated_coloring_without_changing_solver():
    contract = _contract()

    assert contract["settings"]["method"] == "trf"
    assert contract["settings"]["jacobian_mode"] == "colored"
    assert contract["jacobian"]["color_count"] == 15
    assert contract["jacobian"]["central_difference_residual_evaluations_per_matrix"] == 30
    assert contract["jacobian"]["uncolored_equivalent_per_matrix"] == 320


def test_dd223_contract_prohibits_retry_continuation_and_dynamics():
    contract = _contract()
    hard_stops = " ".join(contract["hard_stops"])

    assert contract["nonlinear_solve_attempted"] is False
    assert contract["timestep_attempted"] is False
    assert contract["dynamic_integration_attempted"] is False
    assert "without retry" not in hard_stops.lower()
    assert "retry" in hard_stops.lower()
    assert "continuation" in hard_stops.lower()
