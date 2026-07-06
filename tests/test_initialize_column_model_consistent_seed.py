from importlib.util import module_from_spec, spec_from_file_location
from argparse import Namespace
from pathlib import Path


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "initialize_column_model_consistent_seed.py"
_SPEC = spec_from_file_location("initialize_column_model_consistent_seed", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_candidate_sort_key = _MODULE._candidate_sort_key
_candidate_cmd = _MODULE._candidate_cmd
_choose_best = _MODULE._choose_best
_optimizer_base_cmd = _MODULE._optimizer_base_cmd


def _candidate(name, *, gate=False, max_rel=1.0, tray_total=1000.0, max_abs=1.0):
    return {
        "name": name,
        "audit_summary": {
            "gate_pass": gate,
            "max_relative_rate_per_s": max_rel,
            "max_abs_tray_total_rate_lbmolph": tray_total,
            "max_abs_rate_per_s": max_abs,
        },
    }


def test_choose_best_defaults_to_worst_relative_rate():
    candidates = [
        _candidate("lower_total", max_rel=0.012, tray_total=100.0),
        _candidate("lower_rate", max_rel=0.010, tray_total=900.0),
    ]

    assert _choose_best(candidates, selection="max-rate")["name"] == "lower_rate"


def test_choose_best_prefers_gate_pass_before_metric():
    candidates = [
        _candidate("failed_low_rate", gate=False, max_rel=0.001, tray_total=10.0),
        _candidate("passed_high_rate", gate=True, max_rel=0.010, tray_total=900.0),
    ]

    assert _choose_best(candidates, selection="max-rate")["name"] == "passed_high_rate"


def test_balanced_score_includes_tray_total_residual():
    lower_rate = _candidate("lower_rate", max_rel=0.010, tray_total=1000.0)
    lower_total = _candidate("lower_total", max_rel=0.012, tray_total=10.0)

    assert _candidate_sort_key(lower_total["audit_summary"], selection="balanced") < _candidate_sort_key(
        lower_rate["audit_summary"],
        selection="balanced",
    )


def test_optimizer_base_command_includes_residual_weights(tmp_path):
    args = Namespace(
        stages="interior",
        residual_stages="interior",
        thermo="table",
        runtime_mode="hydraulic",
        condenser_duty_mode="total-condense",
        max_nfev=3,
        max_wall_sec=0.0,
        max_logit_delta=0.25,
        max_flow_log_delta=0.12,
        max_energy_rel_delta=0.15,
        profile_penalty=0.02,
        profile_continuity_penalty=0.05,
        flow_penalty=0.02,
        flow_continuity_penalty=0.05,
        energy_penalty=0.02,
        energy_continuity_penalty=0.02,
        tray_total_penalty=0.25,
        tray_v_residual_weight=3.0,
        tray_l_residual_weight=1.2,
        top_l_residual_weight=0.8,
        bottom_l_residual_weight=0.5,
        bottom_boundary_balance_weight=2.0,
        bottom_boundary_total_weight=1.5,
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
    )

    cmd = _optimizer_base_cmd(
        args,
        input_path=tmp_path / "input.xlsx",
        output_path=tmp_path / "output.xlsx",
        audit_dir=tmp_path / "audit",
    )

    assert "--tray-v-residual-weight" in cmd
    assert "--max-wall-sec" in cmd
    assert cmd[cmd.index("--max-wall-sec") + 1] == "0.0"
    assert cmd[cmd.index("--tray-v-residual-weight") + 1] == "3.0"
    assert "--profile-continuity-penalty" in cmd
    assert cmd[cmd.index("--profile-continuity-penalty") + 1] == "0.05"
    assert "--flow-continuity-penalty" in cmd
    assert "--energy-continuity-penalty" in cmd
    assert "--tray-l-residual-weight" in cmd
    assert "--top-l-residual-weight" in cmd
    assert "--bottom-l-residual-weight" in cmd
    assert "--bottom-boundary-balance-weight" in cmd
    assert cmd[cmd.index("--bottom-boundary-balance-weight") + 1] == "2.0"
    assert "--bottom-boundary-total-weight" in cmd


def test_bottom_boundary_candidate_varies_bottom_boundary_flows(tmp_path):
    args = Namespace(
        stages="interior",
        residual_stages="interior",
        thermo="table",
        runtime_mode="hydraulic",
        condenser_duty_mode="total-condense",
        max_nfev=3,
        max_wall_sec=0.0,
        max_logit_delta=0.25,
        max_flow_log_delta=0.12,
        max_energy_rel_delta=0.15,
        profile_penalty=0.02,
        profile_continuity_penalty=0.05,
        flow_penalty=0.02,
        flow_continuity_penalty=0.05,
        boundary_penalty=0.02,
        energy_penalty=0.02,
        energy_continuity_penalty=0.02,
        tray_total_penalty=0.25,
        tray_v_residual_weight=3.0,
        tray_l_residual_weight=3.0,
        top_l_residual_weight=1.0,
        bottom_l_residual_weight=3.0,
        bottom_boundary_balance_weight=2.0,
        bottom_boundary_total_weight=1.0,
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
        reflux_ratio=2.5,
    )

    cmd = _candidate_cmd(
        args,
        name="bottom-boundary-balanced",
        input_path=tmp_path / "input.xlsx",
        output_path=tmp_path / "output.xlsx",
        audit_dir=tmp_path / "audit",
    )

    assert "--chemsep-product-specs" in cmd
    assert "--vary-bottom-liquid" in cmd
    assert "--vary-boilup" in cmd
    assert "--vary-bottoms" in cmd
    assert cmd[cmd.index("--residual-state-blocks") + 1] == "tray_V,tray_L,top_L,bottom_L"
