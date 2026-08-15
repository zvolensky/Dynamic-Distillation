from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import probe_core_v3_dd223_hydraulic_derivative as dd227


def test_dd227_infers_one_generic_local_target_from_dd226():
    localization = {
        "endpoints": {
            "a": {
                "finite_difference_step_comparison": {
                    "maximum_difference_residual": "francis_hydraulics[interior_1]",
                    "maximum_difference_coordinate": "T[interior_1]",
                }
            },
            "b": {
                "finite_difference_step_comparison": {
                    "maximum_difference_residual": "francis_hydraulics[interior_1]",
                    "maximum_difference_coordinate": "T[interior_1]",
                }
            },
        }
    }

    assert dd227._target_from_localization(localization) == (
        "francis_hydraulics[interior_1]",
        "T[interior_1]",
    )


def test_dd227_preparation_is_read_only_and_freezes_four_steps(tmp_path):
    contract = dd227.prepare(tmp_path / "dd227_contract.json")

    assert contract["steps"] == [2.0e-5, 1.0e-5, 5.0e-6, 2.5e-6]
    assert contract["provider_calls_during_preparation"] == 0
    assert not contract["nonlinear_solve_attempted"]
    assert not contract["state_changed"]
    assert not contract["timestep_attempted"]
    assert not contract["dynamic_integration_attempted"]
