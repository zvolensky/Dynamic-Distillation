from __future__ import annotations

import json
import numpy as np

from dynamic_distillation.core_v3.end_of_run_summary_v1 import (
    build_end_of_run_summary,
    format_end_of_run_summary,
)
from dynamic_distillation.core_v3.report_summary_v2 import (
    REPORT_SCHEMA_VERSION,
    build_report_summary_from_tabular_v2,
    build_report_summary_v2,
    format_report_summary_v2,
)
from dynamic_distillation.core_v3.report_comparison_v1 import (
    compare_report_summaries,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (
    terminal_geometry_from_specs,
)


def test_end_of_run_summary_is_component_and_topology_ledger_driven():
    volumes = ("top", "tray_a", "feed", "tray_b", "bottom")
    components = ("A", "B")
    time = np.asarray([0.0, 60.0])
    liquid = np.full((2, 5, 2), 10.0)
    vapor = np.full((2, 5, 2), 0.5)
    temperature = np.tile(np.linspace(100.0, 140.0, 5), (2, 1))
    pressure = np.tile(np.linspace(15.0, 20.0, 5), (2, 1))
    liquid_flow = np.full((2, 3), 100.0)
    vapor_flow = np.full((2, 4), 120.0)
    geometry = terminal_geometry_from_specs(
        {
            "Top Drum Diameter (ft)": 4.0,
            "Top Drum Length (ft)": 10.0,
            "Bottom Sump Diameter (ft)": 4.0,
            "Bottom Sump Height (ft)": 10.0,
        }
    )

    summary = build_end_of_run_summary(
        component_names=components,
        volume_ids=volumes,
        node_types=("reflux_drum", "tray", "feed_tray", "tray", "reboiler_sump"),
        time_sec=time,
        liquid_component_inventory_lbmol=liquid,
        vapor_component_inventory_lbmol=vapor,
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        hydraulic_volume_ids=volumes[1:-1],
        vapor_flow_lbmolph=vapor_flow,
        vapor_links=(
            ("bottom", "tray_b", "v4"),
            ("tray_b", "feed", "v3"),
            ("feed", "tray_a", "v2"),
            ("tray_a", "top", "v1"),
        ),
        condenser_duty_BTUph=np.asarray([-1000.0, -1000.0]),
        reboiler_duty_BTUph=1100.0,
        reflux_lbmolph=80.0,
        distillate_lbmolph=40.0,
        bottoms_lbmolph=60.0,
        feed_component_lbmolph=(50.0, 50.0),
        final_liquid_density_lbmol_ft3=np.ones(5),
        final_liquid_enthalpy_BTU_lbmol=np.linspace(-100.0, -80.0, 5),
        final_vapor_enthalpy_BTU_lbmol=np.linspace(10.0, 30.0, 5),
        terminal_geometry=geometry,
    )

    assert summary["duties"] == {
        "condenser_BTUph": -1000.0,
        "reboiler_BTUph": 1100.0,
    }
    assert summary["products"]["distillate"]["mole_fraction"] == {
        "A": 0.5,
        "B": 0.5,
    }
    assert summary["steady_state"]["score"] == 0.0
    assert summary["steady_state"]["steady"]
    assert len(summary["profiles"]) == 5
    assert summary["profiles"][0]["liquid_flow_out_lbmolph"] == 80.0
    assert summary["profiles"][-1]["liquid_flow_out_lbmolph"] == 60.0
    rendered = format_end_of_run_summary(summary)
    assert "FINAL TRAY PROFILES" in rendered
    assert rendered.splitlines()[-1].startswith("5 | bottom | reboiler_sump")
    report = build_report_summary_v2(summary)
    assert report["profile_assessment"]["feed_stage"] == 3
    assert report["profile_assessment"]["top_to_bottom_pressure_drop_psia"] == 5.0


def test_report_v2_makes_missing_evidence_and_controlling_steady_term_explicit():
    summary = {
        "schema_id": "core-v3-end-of-run-summary-v1",
        "time_sec": 30.0,
        "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [],
        "steady_state": {
            "steady": False, "score": 2.0,
            "terms": {"temperature_rate": 2.0, "relative_state_rate": 0.5},
            "raw": {},
        },
    }
    report = build_report_summary_v2(
        summary, metadata={
            "pass_gate": True,
            "gates": {"RESIDUAL-INFINITY-NORM": False},
            "final_endpoint": {"scaled_residual_inf_norm": 2.0e-8},
        }
    )
    assert report["report_schema_version"] == REPORT_SCHEMA_VERSION
    assert report["overall_status"] == "FAIL"
    assert report["verdict_reasons"][0]["check_id"] == "RESIDUAL-INFINITY-NORM"
    assert report["verdict_reasons"][0]["observed"] == 2.0e-8
    assert report["verdict_reasons"][0]["limit"] == 1.0e-8
    assert report["verdict_reasons"][1]["check_id"] == "SS-temperature_rate"
    assert report["initial_final_delta"][0]["final"]["data_state"] == "not_available"
    assert "Event timeline: not available" in format_report_summary_v2(report)


def test_report_v2_old_schema_and_missing_artifacts_remain_readable(tmp_path):
    missing = tmp_path / "not_written.jsonl"
    report = build_report_summary_v2(
        {
            "schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 60.0,
            "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [],
            "steady_state": {"steady": True, "score": 0.0, "terms": {}, "raw": {}},
        },
        metadata={"report_events_jsonl": missing, "profile_csv": missing},
    )
    assert report["source_summary_schema"] == "core-v3-end-of-run-summary-v1"
    assert report["events"]["data_state"] == "not_available"
    assert all(item["status"] == "referenced_not_found" for item in report["artifacts"])


def test_report_v2_transient_continuation_fixture_preserves_lineage(tmp_path):
    trajectory = tmp_path / "continuation.jsonl"
    trajectory.write_text(
        "\n".join(json.dumps(row) for row in (
            {"time_sec": 0.5, "nfev": 10, "njev": 2},
            {"time_sec": 1.0, "nfev": 11, "njev": 2},
        )) + "\n",
        encoding="utf-8",
    )
    report = build_report_summary_v2(
        {
            "schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 1.0,
            "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [],
            "steady_state": {
                "steady": False, "score": 1.5,
                "terms": {"temperature_rate": 1.5}, "raw": {},
            },
        },
        metadata={
            "pass_gate": True,
            "started_from_checkpoint": "accepted_seed.npz",
            "report_trajectory_jsonl": trajectory,
        },
    )
    assert report["overall_status"] == "REVIEW"
    assert report["provenance"]["source_checkpoint"] == "accepted_seed.npz"
    assert report["verdict_reasons"][0]["check_id"] == "SS-temperature_rate"
    assert report["numerical_health"]["accepted_steps"] == 2


def test_report_v2_uses_history_for_initial_final_delta_without_endpoint_fallback():
    summary = {
        "schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 60.0,
        "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [],
        "steady_state": {"steady": True, "score": 0.0, "terms": {}, "raw": {}},
    }
    report = build_report_summary_v2(
        summary,
        trajectory={"distillate_flow_lbmolph": np.asarray([10.0, 12.0])},
    )
    distillate = report["initial_final_delta"][0]
    assert distillate["initial"]["value"] == 10.0
    assert distillate["final"]["value"] == 12.0
    assert distillate["change"]["value"] == 2.0


def test_report_v2_tabular_adapter_preserves_history_and_legacy_limits():
    report = build_report_summary_from_tabular_v2(
        [
            {"time_s": 0.0, "D_lbmolph": 10.0, "B_lbmolph": 20.0, "Q_cond_used_BTUph": -100.0},
            {"time_s": 60.0, "D_lbmolph": 12.0, "B_lbmolph": 18.0, "Q_cond_used_BTUph": -110.0, "steady_state_score": 2.0, "steady_state_flag": 0.0, "ss_max_temp_rate_F_per_s": 0.3},
        ],
        metadata={"pass_gate": True},
    )
    assert report["source_summary_schema"] == "core-v3-summary-csv-adapter-v1"
    assert report["initial_final_delta"][0]["change"]["value"] == 2.0
    assert report["steady_state"]["terms"]["temperature_rate"] == 2.0


def test_report_v2_reads_persisted_event_controller_and_balance_evidence(tmp_path):
    trajectory = tmp_path / "trajectory.jsonl"
    events = tmp_path / "events.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    trajectory.write_text(
        "\n".join(json.dumps(row) for row in (
            {"time_sec": 0.0, "nfev": 8, "njev": 2, "retry_attempted": False, "controllers": {"drum_level": {"pv": 0.4, "sp": 0.5, "output_lbmolph": 10.0}}},
            {"time_sec": 10.0, "nfev": 12, "njev": 3, "retry_attempted": True, "controllers": {"drum_level": {"pv": 0.5, "sp": 0.5, "output_lbmolph": 11.0}}},
        )) + "\n", encoding="utf-8"
    )
    events.write_text(json.dumps({"event_id": "b", "time_sec": 10.0, "event_type": "feed_change"}) + "\n" + json.dumps({"event_id": "a", "time_sec": 0.0, "event_type": "checkpoint_restore"}) + "\n", encoding="utf-8")
    ledger.write_text(
        json.dumps({"time_sec": 10.0, "volume": "global_column", "quantity": "A", "residual": 2.0, "normalized_residual": 0.02})
        + "\n"
        + json.dumps({"time_sec": 10.0, "volume": "tray_1", "quantity": "energy", "residual": 1.0, "normalized_residual": 0.01})
        + "\n", encoding="utf-8"
    )
    report = build_report_summary_v2(
        {"schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 10.0, "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [], "steady_state": {"steady": True, "score": 0.0, "terms": {}, "raw": {}}},
        metadata={
            "report_trajectory_jsonl": trajectory,
            "report_events_jsonl": events,
            "report_balance_ledger_jsonl": ledger,
            "console_log": events,
            "controller_tuning": {"drum_kc": 4.0, "drum_ti_sec": 120.0},
            "controller_output_bounds": {"drum_level": {"lower": 10.0, "upper": 11.0}},
            "controller_settling_tolerance": {"drum_level": 0.01},
        },
    )
    assert np.isclose(report["controllers"][0]["integral_absolute_error"], 0.5)
    assert np.isclose(report["controllers"][0]["mean_absolute_error"], 0.05)
    assert np.isclose(report["controllers"][0]["overshoot"], 0.0)
    assert np.isclose(report["controllers"][0]["undershoot"], -0.1)
    assert report["controllers"][0]["output_units"] == "lbmol/h"
    assert report["controllers"][0]["lower_saturation_time_sec"] == 0.0
    assert report["controllers"][0]["upper_saturation_time_sec"] == 0.0
    assert report["controllers"][0]["saturation_data_state"] == "observed"
    assert report["controllers"][0]["settling_time_sec"] == 10.0
    assert report["controllers"][0]["settling_data_state"] == "observed"
    assert report["controllers"][0]["tuning"] == {"drum_kc": 4.0, "drum_ti_sec": 120.0}
    assert [item["event_id"] for item in report["events"]["records"]] == ["a", "b"]
    assert report["balances"]["maximum_absolute_residual"] == 2.0
    assert report["balances"]["energy_ledger_rows"] == 1
    assert not report["balances"]["material_has_separate_in_out"]
    assert not report["balances"]["energy_has_separate_in_out"]
    assert report["balances"]["initial_interval"]["time_sec"] == 10.0
    assert report["balances"]["final_interval"]["rows"][0]["quantity"] == "A"
    assert report["numerical_health"]["nonlinear_function_evaluations_total"] == 20
    assert report["numerical_health"]["jacobian_evaluations_total"] == 5
    assert report["numerical_health"]["solver_retry_count"] == 1
    text = format_report_summary_v2(report)
    assert "CONTROLLER PERFORMANCE" in text
    assert "max/mean abs error" in text
    assert "NUMERICAL HEALTH" in text
    assert next(item for item in report["artifacts"] if item["artifact"] == "events")["sha256"]
    assert next(item for item in report["artifacts"] if item["artifact"] == "console_log")["status"] == "available"


def test_report_v2_describes_global_only_energy_ledger_honestly(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "time_sec": 0.5,
                "quantity": "energy",
                "volume": "global",
                "residual": 1.0e-6,
                "normalized_residual": 1.0e-9,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = build_report_summary_v2(
        {
            "schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 0.5,
            "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [],
            "steady_state": {"steady": False, "score": 2.0, "terms": {}, "raw": {}},
        },
        metadata={"report_balance_ledger_jsonl": ledger},
    )
    assert "global component and energy" in report["balances"]["detail"]
    assert "per-volume energy" not in report["balances"]["detail"]


def test_report_v2_summarizes_balance_residuals_with_declared_tolerance(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        "\n".join(json.dumps(row) for row in (
            {"time_sec": 0.0, "volume": "global", "quantity": "A", "residual": 1.0, "normalized_residual": 0.1},
            {"time_sec": 10.0, "volume": "global", "quantity": "A", "residual": 3.0, "normalized_residual": 0.3},
            {"time_sec": 0.0, "volume": "tray_1", "quantity": "energy", "residual": 2.0, "normalized_residual": 0.2},
            {"time_sec": 10.0, "volume": "tray_1", "quantity": "energy", "residual": 4.0, "normalized_residual": 0.4},
        )) + "\n",
        encoding="utf-8",
    )
    report = build_report_summary_v2(
        {"schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 10.0, "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [], "steady_state": {"steady": True, "score": 0.0, "terms": {}, "raw": {}}},
        metadata={"report_balance_ledger_jsonl": ledger, "report_balance_tolerance": {"absolute": 5.0, "normalized": 0.5}},
    )
    summaries = {item["quantity"]: item for item in report["balances"]["summaries"]}
    assert summaries["A"]["integrated_absolute_residual"] == 20.0
    assert summaries["energy"]["integrated_absolute_residual"] == 30.0
    assert summaries["energy"]["worst_time_sec"] == 10.0
    assert summaries["energy"]["worst_location"] == "tray_1"
    assert summaries["total material"]["final_window_maximum_absolute_residual"] == 3.0
    assert summaries["total material"]["status"] == "PASS"


def test_report_comparison_keeps_missing_kpis_unevaluated():
    baseline = {"run_id": "base", "overall_status": "PASS", "initial_final_delta": [{"variable": "Distillate flow", "final": {"value": 10.0, "data_state": "observed"}}], "constraints": [{"check": "solver residual", "status": "PASS"}]}
    candidate = {"run_id": "candidate", "overall_status": "REVIEW", "initial_final_delta": [{"variable": "Distillate flow", "final": {"value": 12.0, "data_state": "observed"}}, {"variable": "Bottoms flow", "final": {"value": None, "data_state": "not_available"}}], "constraints": [{"check": "solver residual", "status": "REVIEW"}]}
    comparison = compare_report_summaries(baseline, candidate)
    assert next(
        item for item in comparison["kpi_deltas"]
        if item["metric"] == "Distillate flow"
    )["delta"] == 2.0
    assert comparison["constraint_changes"][0]["changed"]


def test_core_v3_word_report_failure_is_nonfatal(monkeypatch, tmp_path):
    from tools import core_v3_water_methanol_vtpr_dynamic_support as support
    import dynamic_distillation.run_report_v1 as report_module

    def fail(*_args, **_kwargs):
        raise RuntimeError("intentional docx failure")

    monkeypatch.setattr(report_module, "generate_core_v3_run_report", fail)
    metadata = {}
    summary = {
        "schema_id": "core-v3-end-of-run-summary-v1", "time_sec": 60.0,
        "duties": {}, "products": {}, "terminal_levels": {}, "profiles": [],
        "steady_state": {"steady": True, "score": 0.0, "terms": {}, "raw": {}},
    }
    assert support.write_core_v3_docx_report(summary, tmp_path / "report.docx", title="test", metadata=metadata) is None
    assert "intentional docx failure" in metadata["word_report_error"]
