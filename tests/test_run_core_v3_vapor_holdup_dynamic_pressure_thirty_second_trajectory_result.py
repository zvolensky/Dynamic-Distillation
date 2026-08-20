import json

from tools import run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory as dd274


def test_dd274_result_passes_frozen_pressure_dynamic_contract() -> None:
    report = json.loads((dd274.ROOT / dd274.RESULT).read_text(encoding="utf-8"))
    assert report["pass_gate"]
    assert all(report["gates"].values())
    assert len(report["nominal_endpoints"]) == 120
    assert len(report["refined_endpoints"]) == 2
    assert report["pressure_controller_active"] is False
    initial = report["pressure_time_series"][0]
    final = report["nominal_endpoints"][-1]
    assert final["reflux_drum_pressure_psia"] != initial["reflux_drum_pressure_psia"]
    assert final["top_tray_pressure_psia"] > final["reflux_drum_pressure_psia"]
    assert final["bottom_pressure_psia"] > final["top_tray_pressure_psia"]
    assert final["fixed_duty_relative_error"] < 1.0e-10
    assert final["scaled_residual_inf_norm"] < 1.0e-8
