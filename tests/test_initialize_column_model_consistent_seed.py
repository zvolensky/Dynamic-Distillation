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
_dynamic_gate_eval_cmd = _MODULE._dynamic_gate_eval_cmd
_dynamic_run_cmd = _MODULE._dynamic_run_cmd
_checkpoint_reload_gate_eval_cmd = _MODULE._checkpoint_reload_gate_eval_cmd
_powershell_command_text = _MODULE._powershell_command_text
_safe_case_name = _MODULE._safe_case_name
_clean_usable_assessment = _MODULE._clean_usable_assessment
_accepted_artifact_summary = _MODULE._accepted_artifact_summary
_accepted_artifact_run_command = _MODULE._accepted_artifact_run_command
_dynamic_run_artifacts = _MODULE._dynamic_run_artifacts
_final_status = _MODULE._final_status
InitializerExecutionLog = _MODULE.InitializerExecutionLog


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
        bottom_vapor_interface_weight=0.75,
        vflow_energy_closure_weight=1.25,
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
    assert "--bottom-vapor-interface-weight" in cmd
    assert cmd[cmd.index("--bottom-vapor-interface-weight") + 1] == "0.75"
    assert "--vflow-energy-closure-weight" in cmd
    assert cmd[cmd.index("--vflow-energy-closure-weight") + 1] == "1.25"


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
        bottom_vapor_interface_weight=0.75,
        vflow_energy_closure_weight=0.5,
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


def test_safe_case_name_removes_path_unfriendly_characters():
    assert _safe_case_name("C3/C4 splitter case", "fallback") == "C3_C4_splitter_case"
    assert _safe_case_name("!!!", "fallback case") == "case"


def test_initializer_execution_log_writes_required_milestone_shape(tmp_path):
    args = Namespace(
        thermo="table",
        runtime_mode="hydraulic",
        condenser_duty_mode="total-condense",
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
        selection="max-rate",
        candidates="coupled-vle-topL",
    )
    log_path = tmp_path / "initializer_case_20260708_120000.log"
    log = InitializerExecutionLog(
        log_path,
        input_path=tmp_path / "seed.xlsx",
        output_path=tmp_path / "out.xlsx",
        case_name="case",
        args=args,
    )
    log.milestone("initial_residual_evaluation", "OK", max_relative_rate_per_s=0.1, worst_block="tray_V")
    log.close("REJECTED_RESIDUAL_GATE", selected="candidate")

    text = log_path.read_text(encoding="utf-8")
    assert "INITIALIZER EXECUTION LOG" in text
    assert "git_commit=" in text
    assert "milestone=initial_residual_evaluation" in text
    assert "max_relative_rate_per_s=0.1" in text
    assert "milestone=final_decision" in text


def test_powershell_command_text_quotes_paths_with_spaces_and_quotes():
    text = _powershell_command_text(
        [
            "python",
            "-m",
            "dynamic_distillation.dynamic_run_scaffold_v1",
            "--excel",
            r"C:\Users\Thomas Zvolensky\seed file.xlsx",
            "--case-name",
            "Tom's case",
        ]
    )

    assert r"'C:\Users\Thomas Zvolensky\seed file.xlsx'" in text
    assert "'Tom''s case'" in text


def test_clean_usable_assessment_accepts_residual_only_pass():
    assessment = _clean_usable_assessment(
        selected_audit={"gate_pass": True},
        dynamic_gate_report={"enabled": False, "passed": None},
        dynamic_gate_enabled=False,
    )

    assert assessment["usable"] is True
    assert assessment["basis"] == "residual_gate_only"
    assert assessment["dynamic_gate_required_for_final_acceptance"] is True


def test_clean_usable_assessment_rejects_residual_gate_failure():
    assessment = _clean_usable_assessment(
        selected_audit={"gate_pass": False},
        dynamic_gate_report={"enabled": True, "passed": True},
        dynamic_gate_enabled=True,
    )

    assert assessment["usable"] is False
    assert assessment["reason"] == "residual gate failed"
    assert assessment["residual_gate_pass"] is False


def test_clean_usable_assessment_reports_first_dynamic_gate_failure():
    assessment = _clean_usable_assessment(
        selected_audit={"gate_pass": True},
        dynamic_gate_report={
            "enabled": True,
            "passed": False,
            "candidates": [
                {
                    "checks": [
                        {"name": "final_score_ratio", "passed": True},
                        {"name": "peak_score_ratio", "passed": False, "value": 4.0},
                    ]
                }
            ],
        },
        dynamic_gate_enabled=True,
    )

    assert assessment["usable"] is False
    assert assessment["dynamic_gate_pass"] is False
    assert assessment["reason"] == "dynamic gate failed: peak_score_ratio"
    assert assessment["failed_dynamic_check"]["value"] == 4.0


def test_dynamic_run_artifacts_reads_native_checkpoint_from_metadata(tmp_path):
    checkpoint = tmp_path / "accepted.npz"
    checkpoint.write_bytes(b"checkpoint")
    workbook = tmp_path / "restart.xlsx"
    workbook.write_bytes(b"workbook")
    metadata = tmp_path / "run_metadata_20260708_120000.json"
    metadata.write_text(
        """{
  "run_id": "abc",
  "status": "completed",
  "final_time_s": 12.5,
  "summary_csv": "summary.csv",
  "profile_csv": "profile.csv",
  "restart_workbook": "%s",
  "native_checkpoint": "%s"
}
"""
        % (str(workbook).replace("\\", "\\\\"), str(checkpoint).replace("\\", "\\\\")),
        encoding="utf-8",
    )

    artifacts = _dynamic_run_artifacts(tmp_path)

    assert artifacts["run_metadata_json"] == str(metadata)
    assert artifacts["native_checkpoint"] == str(checkpoint)
    assert artifacts["native_checkpoint_exists"] is True
    assert artifacts["restart_workbook_exists"] is True
    assert artifacts["run_id"] == "abc"


def test_accepted_artifact_prefers_checkpoint_when_usable(tmp_path):
    output = tmp_path / "selected.xlsx"
    output.write_bytes(b"workbook")
    checkpoint = tmp_path / "accepted.npz"
    checkpoint.write_bytes(b"checkpoint")

    artifact = _accepted_artifact_summary(
        clean_assessment={"usable": True, "reason": "passed"},
        selected_workbook=tmp_path / "candidate.xlsx",
        output_workbook=output,
        dynamic_artifacts={"native_checkpoint": str(checkpoint), "native_checkpoint_exists": True},
    )

    assert artifact["status"] == "accepted"
    assert artifact["preferred_kind"] == "native_checkpoint"
    assert artifact["preferred_path"] == str(checkpoint)


def test_accepted_artifact_marks_failed_candidate_diagnostic_only(tmp_path):
    output = tmp_path / "selected.xlsx"
    output.write_bytes(b"workbook")

    artifact = _accepted_artifact_summary(
        clean_assessment={"usable": False, "reason": "dynamic gate failed"},
        selected_workbook=tmp_path / "candidate.xlsx",
        output_workbook=output,
        dynamic_artifacts={},
    )

    assert artifact["status"] == "diagnostic_only"
    assert artifact["preferred_kind"] == "workbook"
    assert artifact["reason"] == "dynamic gate failed"


def test_accepted_artifact_run_command_uses_checkpoint_when_preferred(tmp_path):
    args = Namespace(
        runtime_mode="hydraulic",
        thermo="table",
        condenser_duty_mode="total-condense",
        dynamic_gate_n_steps=10,
        dynamic_gate_dt=0.2,
        dynamic_gate_log_every=5,
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
        dynamic_run_extra_arg=[],
        dynamic_run_extra_args="",
    )
    checkpoint = tmp_path / "accepted.npz"
    checkpoint.write_bytes(b"checkpoint")

    cmd = _accepted_artifact_run_command(
        args,
        output_workbook=tmp_path / "selected.xlsx",
        accepted_artifact={
            "preferred_kind": "native_checkpoint",
            "native_checkpoint": str(checkpoint),
            "native_checkpoint_exists": True,
        },
        logs_dir=tmp_path / "restart",
    )

    assert "--init-from-checkpoint" in cmd
    assert cmd[cmd.index("--init-from-checkpoint") + 1] == str(checkpoint)


def test_accepted_artifact_run_command_omits_checkpoint_for_workbook_artifact(tmp_path):
    args = Namespace(
        runtime_mode="hydraulic",
        thermo="table",
        condenser_duty_mode="total-condense",
        dynamic_gate_n_steps=10,
        dynamic_gate_dt=0.2,
        dynamic_gate_log_every=5,
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
        dynamic_run_extra_arg=[],
        dynamic_run_extra_args="",
    )

    cmd = _accepted_artifact_run_command(
        args,
        output_workbook=tmp_path / "selected.xlsx",
        accepted_artifact={
            "preferred_kind": "workbook",
            "native_checkpoint": "",
            "native_checkpoint_exists": False,
        },
        logs_dir=tmp_path / "restart",
    )

    assert "--init-from-checkpoint" not in cmd


def test_final_status_rejects_when_dynamic_passes_but_clean_assessment_fails():
    status = _final_status(
        dynamic_gate_enabled=True,
        clean_assessment={"usable": False},
        residual_gate_pass=False,
        checkpoint_reload_gate_enabled=False,
        checkpoint_reload_gate_report={"passed": None},
    )

    assert status == "REJECTED_DYNAMIC_GATE"


def test_final_status_rejects_checkpoint_reload_failure_after_clean_pass():
    status = _final_status(
        dynamic_gate_enabled=True,
        clean_assessment={"usable": True},
        residual_gate_pass=True,
        checkpoint_reload_gate_enabled=True,
        checkpoint_reload_gate_report={"passed": False},
    )

    assert status == "REJECTED_CHECKPOINT_RELOAD_GATE"


def test_final_status_ignores_skipped_checkpoint_reload_for_failed_clean_candidate():
    status = _final_status(
        dynamic_gate_enabled=True,
        clean_assessment={"usable": False},
        residual_gate_pass=False,
        checkpoint_reload_gate_enabled=True,
        checkpoint_reload_gate_report={"passed": None, "reason": "skipped because candidate is not clean usable"},
    )

    assert status == "REJECTED_DYNAMIC_GATE"


def test_dynamic_run_command_includes_runtime_and_extra_args(tmp_path):
    args = Namespace(
        runtime_mode="hydraulic",
        thermo="table",
        condenser_duty_mode="total-condense",
        dynamic_gate_n_steps=10,
        dynamic_gate_dt=0.2,
        dynamic_gate_log_every=5,
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
        dynamic_run_extra_arg=["--disable-startup-thermo-conditioning", "--disable-restart-reentry-settling"],
        dynamic_run_extra_args="--vapor-flow-relaxation-sec 0",
    )

    cmd = _dynamic_run_cmd(args, excel=tmp_path / "seed.xlsx", logs_dir=tmp_path / "run")

    assert "dynamic_distillation.dynamic_run_scaffold_v1" in cmd
    assert "--excel" in cmd
    assert cmd[cmd.index("--n-steps") + 1] == "10"
    assert "--include-energy" in cmd
    assert "--use-excel-vapor-holdup" in cmd
    assert "--no-equilibrium" in cmd
    assert "--no-flash-feed-at-stage-conditions" in cmd
    assert "--disable-startup-thermo-conditioning" in cmd
    assert "--disable-restart-reentry-settling" in cmd
    assert "--vapor-flow-relaxation-sec" in cmd
    assert cmd[cmd.index("--vapor-flow-relaxation-sec") + 1] == "0"


def test_dynamic_run_command_can_load_native_checkpoint(tmp_path):
    args = Namespace(
        runtime_mode="hydraulic",
        thermo="table",
        condenser_duty_mode="total-condense",
        dynamic_gate_n_steps=10,
        dynamic_gate_dt=0.2,
        dynamic_gate_log_every=5,
        include_energy=True,
        use_excel_vapor_holdup=True,
        no_equilibrium=True,
        no_flash_feed_at_stage_conditions=True,
        dynamic_run_extra_arg=[],
        dynamic_run_extra_args="",
    )
    checkpoint = tmp_path / "accepted.npz"

    cmd = _dynamic_run_cmd(
        args,
        excel=tmp_path / "seed.xlsx",
        logs_dir=tmp_path / "run",
        init_checkpoint=checkpoint,
    )

    assert "--init-from-checkpoint" in cmd
    assert cmd[cmd.index("--init-from-checkpoint") + 1] == str(checkpoint)


def test_dynamic_gate_eval_command_includes_limits(tmp_path):
    args = Namespace(
        dynamic_gate_max_final_score_ratio=1.0,
        dynamic_gate_max_peak_score_ratio=2.0,
        dynamic_gate_max_final_rel_rate_ratio=1.5,
        dynamic_gate_max_peak_rel_rate_ratio=2.5,
        dynamic_gate_max_time_s=60.0,
        dynamic_gate_max_final_temp_rate_ratio=3.0,
        dynamic_gate_endpoint_drift_limit=["P_top_psia=0.5"],
        dynamic_gate_summary_ratio_limit=["pv_inner_dv_max_lbmolph=1.2"],
    )

    cmd = _dynamic_gate_eval_cmd(
        args,
        baseline_summary=tmp_path / "baseline.csv",
        candidate_summary=tmp_path / "candidate.csv",
        candidate_label="candidate-a",
        output_json=tmp_path / "gate.json",
        output_md=tmp_path / "gate.md",
    )

    assert "--baseline-summary" in cmd
    assert "--candidate-summary" in cmd
    assert cmd[cmd.index("--candidate-label") + 1] == "candidate-a"
    assert cmd[cmd.index("--max-time-s") + 1] == "60.0"
    assert "--max-final-temp-rate-ratio" in cmd
    assert "--endpoint-drift-limit" in cmd
    assert "P_top_psia=0.5" in cmd
    assert "--summary-ratio-limit" in cmd
    assert "pv_inner_dv_max_lbmolph=1.2" in cmd


def test_checkpoint_reload_gate_eval_command_uses_parity_limit(tmp_path):
    args = Namespace(
        checkpoint_reload_gate_max_ratio=1.1,
        checkpoint_reload_gate_max_time_s=30.0,
    )

    cmd = _checkpoint_reload_gate_eval_cmd(
        args,
        baseline_summary=tmp_path / "candidate.csv",
        reload_summary=tmp_path / "reload.csv",
        output_json=tmp_path / "reload_gate.json",
        output_md=tmp_path / "reload_gate.md",
    )

    assert "--candidate-label" in cmd
    assert cmd[cmd.index("--candidate-label") + 1] == "checkpoint_reload"
    assert cmd[cmd.index("--max-final-score-ratio") + 1] == "1.1"
    assert cmd[cmd.index("--max-peak-score-ratio") + 1] == "1.1"
    assert cmd[cmd.index("--max-final-rel-rate-ratio") + 1] == "1.1"
    assert cmd[cmd.index("--max-peak-rel-rate-ratio") + 1] == "1.1"
    assert cmd[cmd.index("--max-final-temp-rate-ratio") + 1] == "1.1"
    assert cmd[cmd.index("--max-time-s") + 1] == "30.0"
