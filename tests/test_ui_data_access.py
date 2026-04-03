from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from ui.data_access import _as_list
from ui.data_access import read_runner_phase
from ui.data_access import validate_excel_input


def test_as_list_handles_numpy_array_without_truthiness_error() -> None:
    vals = np.asarray([1.0, 2.0, 3.0], dtype=float)
    assert _as_list(vals) == [1.0, 2.0, 3.0]


def test_validate_excel_input_reports_loader_failure(monkeypatch, tmp_path: Path) -> None:
    excel = tmp_path / "bad.xlsx"
    excel.write_bytes(b"x")
    monkeypatch.setattr("ui.data_access.load_case_from_excel", lambda path: (_ for _ in ()).throw(ValueError("bad load")))
    report = validate_excel_input(excel)
    assert report["ok"] is False
    assert any("Excel load failed" in msg for msg in report["errors"])


def test_validate_excel_input_reports_validator_output(monkeypatch, tmp_path: Path) -> None:
    excel = tmp_path / "ok.xlsx"
    excel.write_bytes(b"x")
    dummy_case = object()
    dummy_col = object()

    class _Report:
        ok = False
        errors = ["e1"]
        warnings = ["w1"]

    monkeypatch.setattr("ui.data_access.load_case_from_excel", lambda path: dummy_case)
    monkeypatch.setattr("ui.data_access.build_column_spec_from_case", lambda case: dummy_col)
    monkeypatch.setattr("ui.data_access.validate_loaded_case", lambda case, col: _Report())
    report = validate_excel_input(excel)
    assert report["ok"] is False
    assert report["errors"] == ["e1"]
    assert report["warnings"] == ["w1"]


def test_read_runner_phase_detects_startup(tmp_path: Path) -> None:
    log = tmp_path / "runner_stdout.log"
    log.write_text(
        "[Milestone] built inputs and thermo provider  wall=    0.44 s\n"
        "[Init] Thermo startup conditioning  success=True\n",
        encoding="utf-8",
    )
    phase = read_runner_phase(log)
    assert phase["phase"] == "startup"
    assert phase["startup_in_progress"] is True
    assert "Startup in progress" in phase["message"]


def test_read_runner_phase_detects_integration(tmp_path: Path) -> None:
    log = tmp_path / "runner_stdout.log"
    log.write_text(
        "[Milestone] opened log files  wall=  725.62 s\n"
        "[Progress] step=   150  sim_t=     30.00 s  wall=    104.12 s\n",
        encoding="utf-8",
    )
    phase = read_runner_phase(log)
    assert phase["phase"] == "integration"
    assert phase["integration_started"] is True
    assert "Integration running" in phase["message"]
