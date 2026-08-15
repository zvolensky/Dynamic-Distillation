from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_full_c3c4_aligned_density_root as dd231


def test_dd231_contract_freezes_corrected_density_scale_and_two_starts(tmp_path):
    contract = dd231.prepare(tmp_path / "dd231_contract.json")

    assert len(contract["starts"]) == 2
    assert len(contract["coordinate_scale"]) == 160
    assert contract["provider_routing"]["declared_liquid_density"] == "aligned_pr_smallest_positive_root"
    assert contract["settings"]["jacobian_mode"] == "colored"
    assert contract["provider_calls_during_preparation"] == 0
    assert not contract["nonlinear_solve_attempted"]
    assert not contract["timestep_attempted"]
    assert not contract["dynamic_integration_attempted"]
