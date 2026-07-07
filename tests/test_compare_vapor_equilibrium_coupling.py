from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "compare_vapor_equilibrium_coupling.py"
_SPEC = spec_from_file_location("compare_vapor_equilibrium_coupling", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

compare_profiles = _MODULE.compare_profiles


def _row(**updates):
    base = {
        "time_s": "40",
        "stage": "1",
        "node_type": "stage",
        "x_A": "0.5",
        "x_B": "0.5",
        "y_A": "0.8",
        "y_B": "0.2",
        "K_state_A": "1.6",
        "K_state_B": "0.4",
        "K_thermo_A": "1.2",
        "K_thermo_B": "0.8",
        "stage_energy_balance_resid_BTUps": "10",
        "dT_energy_raw_F_per_s": "0.1",
        "tray_effective_heat_capacity_BTU_per_F": "100",
        "P_psia_hyd": "100",
        "P_from_vapor_holdup_psia": "105",
        "MV_lbmol": "2",
        "tray_vapor_volume_ft3": "100",
        "Z_tray": "0.9",
        "vflow_energy_calc_lbmolph": "120",
        "vflow_energy_used_lbmolph": "100",
        "hydraulic_dp_used_psia": "2",
        "hydraulic_dp_raw_psia": "2",
    }
    base.update(updates)
    return base


def _write_csv(path, rows):
    fields = list(rows[0].keys())
    lines = [",".join(fields)]
    for row in rows:
        lines.append(",".join(str(row.get(field, "")) for field in fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_compare_profiles_ranks_candidate_worsening(tmp_path):
    baseline = tmp_path / "baseline.csv"
    candidate = tmp_path / "candidate.csv"
    _write_csv(
        baseline,
        [
            _row(stage="1", K_state_A="1.2", stage_energy_balance_resid_BTUps="10"),
            _row(stage="2", K_state_A="1.2", vflow_energy_calc_lbmolph="110", vflow_energy_used_lbmolph="100"),
        ],
    )
    _write_csv(
        candidate,
        [
            _row(stage="1", K_state_A="2.4", stage_energy_balance_resid_BTUps="60"),
            _row(stage="2", K_state_A="1.2", vflow_energy_calc_lbmolph="180", vflow_energy_used_lbmolph="100"),
        ],
    )

    report = compare_profiles(baseline, candidate, time_s=40, top_n=3)

    assert report["sections"]["k_state_vs_thermo"]["worst"]["stage_1based"] == 1
    assert report["sections"]["energy_residual"]["worst"]["abs_worsening"] == pytest.approx(50)
    assert report["sections"]["vapor_flow_calc_used"]["worst"]["stage_1based"] == 2
    assert report["sections"]["vapor_flow_calc_used"]["worst"]["abs_worsening"] == pytest.approx(70)


def test_compare_profiles_reports_dominant_family(tmp_path):
    baseline = tmp_path / "baseline.csv"
    candidate = tmp_path / "candidate.csv"
    _write_csv([baseline][0], [_row(vflow_energy_calc_lbmolph="101", vflow_energy_used_lbmolph="100")])
    _write_csv([candidate][0], [_row(vflow_energy_calc_lbmolph="300", vflow_energy_used_lbmolph="100")])

    report = compare_profiles(baseline, candidate, time_s=40, top_n=1)

    assert report["dominant_failure_family"]["family"] == "vapor-flow inconsistency"


def test_compare_profiles_flags_candidate_unit_k_packet(tmp_path):
    baseline = tmp_path / "baseline.csv"
    candidate = tmp_path / "candidate.csv"
    _write_csv(
        baseline,
        [_row(stage="18", K_thermo_A="2.0", K_thermo_B="0.5")],
    )
    _write_csv(
        candidate,
        [_row(stage="18", K_thermo_A="1.0", K_thermo_B="1.0")],
    )

    report = compare_profiles(baseline, candidate, time_s=40, top_n=1)
    worst = report["sections"]["thermo_unit_k_packet"]["worst"]

    assert worst["stage_1based"] == 18
    assert worst["baseline"] == pytest.approx(0.0)
    assert worst["candidate"] == pytest.approx(1.0)
    assert worst["candidate_max_abs_K_thermo_minus_1"] == pytest.approx(0.0)
