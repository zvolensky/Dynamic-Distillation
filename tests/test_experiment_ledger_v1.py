from __future__ import annotations

import csv
from pathlib import Path

from dynamic_distillation.experiment_ledger_v1 import (
    append_run_registry_entry,
    compose_cli_command_identity,
)


def test_compose_cli_command_identity_ignores_ui_metadata_flags() -> None:
    argv_a = [
        "--excel",
        "case.xlsx",
        "--run-name",
        "Alpha",
        "--run-description",
        "First run",
        "--logs-dir",
        "logs/a",
    ]
    argv_b = [
        "--excel",
        "case.xlsx",
        "--run-name",
        "Beta",
        "--run-description",
        "Second run",
        "--logs-dir",
        "logs/b",
    ]
    ident_a = compose_cli_command_identity("dynamic_distillation.dynamic_run_scaffold_v1", argv_a)
    ident_b = compose_cli_command_identity("dynamic_distillation.dynamic_run_scaffold_v1", argv_b)
    assert ident_a == ident_b


def test_append_run_registry_entry_migrates_header_and_writes_run_metadata(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    registry_path = logs_dir / "run_registry.csv"
    registry_path.write_text(
        "run_id,run_datetime_local,recorded_at_local,module_name,command_source,cli_command,argv_json,summary_csv,profile_csv\n",
        encoding="utf-8",
    )
    summary_path = logs_dir / "column_summary_20260329_123456.csv"
    summary_path.write_text("time_s\n0\n", encoding="utf-8")
    profile_path = logs_dir / "column_profile_20260329_123456.csv"
    profile_path.write_text("time_s\n0\n", encoding="utf-8")

    append_run_registry_entry(
        logs_dir=logs_dir,
        module_name="dynamic_distillation.dynamic_run_scaffold_v1",
        argv=["--excel", "case.xlsx", "--run-name", "UI Baseline"],
        summary_csv_path=str(summary_path),
        profile_csv_path=str(profile_path),
        run_name="UI Baseline",
        run_description="Smoke test from UI",
        metadata_json_path=str(logs_dir / "run_metadata_20260329_123456.json"),
    )

    with registry_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    row = rows[-1]
    assert row["run_id"] == "20260329_123456"
    assert row["run_name"] == "UI Baseline"
    assert row["run_description"] == "Smoke test from UI"
    assert row["metadata_json"].endswith("run_metadata_20260329_123456.json")
