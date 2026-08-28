from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.run_manager import active_run_status
from ui.run_manager import build_launch_spec
from ui.run_manager import build_launch_spec_from_cli
from ui.run_manager import request_runtime_extension
from ui.run_manager import runtime_control_path
from ui.run_manager import launch_simulation
from ui.run_manager import is_pid_running
from ui.run_manager import inspect_stored_state
from ui.run_manager import save_uploaded_state_bytes


def test_build_launch_spec_appends_advanced_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 150,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    logs_dir = tmp_path / "logs"

    spec = build_launch_spec(
        excel_path=excel_path,
        run_name="UI Override Test",
        run_description="check command args",
        logs_dir=logs_dir,
        runtime_mode="hydraulic",
        thermo_mode="table-pool",
        thermo_table_path=Path("cache/custom_table.json"),
        thermo_table_anchor_blend_count=6,
        thermo_pool_workers=4,
        thermo_pool_chunk_size=8,
        thermo_every_n_steps=2,
        fast_startup_override=True,
        equilibrium_relaxation_live_pr_override=True,
        include_energy_override=True,
        integrator="bdf",
    )

    cmd = spec.command
    assert "--runtime-mode" in cmd and "hydraulic" in cmd
    assert "--thermo" in cmd and "table-pool" in cmd
    assert "--thermo-table" in cmd
    table_arg = cmd[cmd.index("--thermo-table") + 1]
    assert Path(table_arg).name == "custom_table.json"
    assert "--thermo-table-anchor-blend-count" in cmd and "6" in cmd
    assert "--thermo-pool-workers" in cmd and "4" in cmd
    assert "--thermo-pool-chunk-size" in cmd and "8" in cmd
    assert "--thermo-every" in cmd and "2" in cmd
    assert "--fast-startup" in cmd
    assert "--equilibrium-relaxation-live-pr" in cmd
    assert "--include-energy" in cmd
    assert "--integrator" in cmd and "bdf" in cmd

    assert spec.runtime_mode == "hydraulic"
    assert spec.thermo_mode == "table-pool"
    assert spec.thermo_table_path == Path("cache/custom_table.json")
    assert spec.thermo_table_anchor_blend_count == 6
    assert spec.thermo_pool_workers == 4
    assert spec.thermo_pool_chunk_size == 8
    assert spec.thermo_every_n_steps == 2
    assert spec.fast_startup_override is True
    assert spec.equilibrium_relaxation_live_pr_override is True
    assert spec.include_energy_override is True
    assert spec.integrator == "bdf"


def test_build_launch_spec_emits_explicit_default_thermo_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 150,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    spec = build_launch_spec(
        excel_path=excel_path,
        run_name="Default Thermo",
        run_description="",
    )
    assert "--thermo" in spec.command
    assert spec.command[spec.command.index("--thermo") + 1] == "table-pool"
    assert spec.thermo_mode == "table-pool"


def _write_native_checkpoint(path: Path, *, n_stages: int = 20, n_components: int = 3) -> None:
    metadata = {
        "schema": "dynamic_distillation.native_checkpoint.v1",
        "run_id": "source-run",
        "final_time_s": 30.0,
        "layout": {"n_stages": n_stages, "n_components": n_components},
        "column": {"n_stages": n_stages, "n_components": n_components},
    }
    np.savez_compressed(
        path,
        metadata_json=np.asarray(json.dumps(metadata)),
        final_state=np.asarray([1.0, 2.0]),
    )


def _write_core_v3_checkpoint(path: Path, *, n_stages: int = 20, n_components: int = 3) -> None:
    metadata = {
        "schema": "dynamic_distillation.core_v3_checkpoint.v1",
        "model_id": "core-v3-c3c4-vapor-holdup-dynamic-pressure",
        "final_time_s": 60.0,
        "n_stages": n_stages,
        "n_components": n_components,
    }
    arrays = {
        "liquid_component_inventory_lbmol": np.ones((n_stages, n_components)),
        "vapor_component_inventory_lbmol": np.ones((n_stages, n_components)),
        "temperature_F": np.ones(n_stages),
        "pressure_psia": np.ones(n_stages),
        "previous_coordinates": np.ones(10),
        "controller_memory": np.ones(2),
    }
    np.savez_compressed(path, metadata_json=np.asarray(json.dumps(metadata)), **arrays)


def test_build_launch_spec_uses_core_v3_runner_for_core_checkpoint(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 60.0,
            "n_steps": 300,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    checkpoint_path = tmp_path / "core_v3.npz"
    _write_core_v3_checkpoint(checkpoint_path)

    spec = build_launch_spec(
        excel_path=excel_path,
        initialization_mode="restart",
        checkpoint_path=checkpoint_path,
        run_name="Core V3 UI",
        run_description="latest model",
        core_v3_duration_sec=12.5,
        core_v3_log_every_n_steps=2,
    )

    assert spec.checkpoint_schema == "dynamic_distillation.core_v3_checkpoint.v1"
    assert Path(spec.command[2]).name == "run_core_v3_dynamic.py"
    assert spec.command[spec.command.index("--duration-sec") + 1] == "12.5"
    assert spec.command[spec.command.index("--dt") + 1] == "0.25"
    assert spec.command[spec.command.index("--parallel-workers") + 1] == "8"
    assert spec.n_steps == 50
    assert spec.runtime_mode == "core-v3"
    assert spec.integrator == "implicit-trf"


def test_inspect_stored_state_accepts_core_v3_checkpoint(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "core_v3.npz"
    _write_core_v3_checkpoint(checkpoint_path)

    info = inspect_stored_state(checkpoint_path)

    assert info["compatible"] is True
    assert info["kind"] == "core-v3-checkpoint"
    assert info["n_stages"] == 20
    assert info["n_components"] == 3


def test_build_launch_spec_restart_adds_native_checkpoint(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 60.0,
            "n_steps": 300,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    checkpoint_path = tmp_path / "checkpoint.npz"
    _write_native_checkpoint(checkpoint_path)

    spec = build_launch_spec(
        excel_path=excel_path,
        initialization_mode="restart",
        checkpoint_path=checkpoint_path,
        run_name="Restart Test",
        run_description="",
    )

    assert spec.initialization_mode == "restart"
    assert spec.checkpoint_path == checkpoint_path.resolve()
    assert spec.checkpoint_schema == "dynamic_distillation.native_checkpoint.v1"
    assert "--init-from-checkpoint" in spec.command
    assert spec.command[spec.command.index("--init-from-checkpoint") + 1] == str(checkpoint_path.resolve())


def test_build_launch_spec_restart_rejects_workbook_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 60.0,
            "n_steps": 300,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    checkpoint_path = tmp_path / "checkpoint.npz"
    _write_native_checkpoint(checkpoint_path, n_stages=10)

    with pytest.raises(ValueError, match="does not match the selected workbook"):
        build_launch_spec(
            excel_path=excel_path,
            initialization_mode="restart",
            checkpoint_path=checkpoint_path,
            run_name="Mismatch",
            run_description="",
        )


def test_inspect_stored_state_identifies_core_v3_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "dd274_evidence.npz"
    np.savez_compressed(
        evidence_path,
        nominal_coordinates=np.zeros((2, 4)),
        nominal_times_sec=np.asarray([0.0, 0.25]),
    )

    info = inspect_stored_state(evidence_path)

    assert info["kind"] == "core-v3-evidence"
    assert info["compatible"] is False
    assert "not a reusable native checkpoint" in info["reason"]


def test_save_uploaded_state_bytes_sanitizes_name(tmp_path: Path) -> None:
    saved = save_uploaded_state_bytes("../state.npz", b"payload", uploads_dir=tmp_path)
    assert saved.parent == tmp_path
    assert saved.name.endswith("_state.npz")
    assert saved.read_bytes() == b"payload"


def test_build_launch_spec_emits_dwsim_property_package_when_requested(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 10,
            "n_components": 2,
            "dt_sec": 0.5,
            "log_every_n_steps": 10,
            "t_final_sec": 300.0,
            "n_steps": 600,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    spec = build_launch_spec(
        excel_path=excel_path,
        run_name="UNIFAC",
        run_description="",
        thermo_mode="dwsim",
        dwsim_property_package="unifac",
    )

    assert spec.thermo_mode == "dwsim"
    assert spec.dwsim_property_package == "unifac"
    assert "--dwsim-property-package" in spec.command
    assert spec.command[spec.command.index("--dwsim-property-package") + 1] == "unifac"


def test_build_launch_spec_ignores_thermo_table_for_dwsim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 10,
            "n_components": 2,
            "dt_sec": 0.5,
            "log_every_n_steps": 10,
            "t_final_sec": 300.0,
            "n_steps": 600,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    spec = build_launch_spec(
        excel_path=excel_path,
        run_name="UNIFAC",
        run_description="",
        thermo_mode="dwsim",
        dwsim_property_package="unifac",
        thermo_table_path=Path("cache/custom_table.json"),
    )

    assert spec.thermo_mode == "dwsim"
    assert spec.thermo_table_path is None
    assert "--thermo-table" not in spec.command


def test_build_launch_spec_from_cli_accepts_bare_flags(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.25,
            "log_every_n_steps": 9,
            "t_final_sec": 600.0,
            "n_steps": 2400,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    spec = build_launch_spec_from_cli(
        "--runtime-mode hydraulic --include-energy --thermo table-pool",
        default_excel_path=excel_path,
    )

    cmd = spec.command
    assert cmd[:4] == [sys.executable, "-u", "-m", "dynamic_distillation.dynamic_run_scaffold_v1"]
    assert "--excel" in cmd
    assert cmd[cmd.index("--excel") + 1] == str(excel_path.resolve())
    assert "--logs-dir" in cmd
    assert "--allow-repeat-command" in cmd
    assert spec.run_name == "case"
    assert spec.n_steps == 600
    assert spec.dt_sec == 0.25
    assert spec.log_every_n_steps == 9
    assert spec.runtime_mode == "hydraulic"
    assert spec.thermo_mode == "table-pool"
    assert spec.include_energy_override is True


def test_build_launch_spec_from_cli_accepts_full_runner_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    thermo_table_path = tmp_path / "thermo_table.json"
    thermo_table_path.write_text("{}", encoding="utf-8")
    logs_dir = tmp_path / "custom_logs"

    spec = build_launch_spec_from_cli(
        (
            f'python -m dynamic_distillation.dynamic_run_scaffold_v1 '
            f'--excel "{excel_path}" '
            f'--run-name "CLI Run" '
            f'--n-steps 42 --dt 0.5 --log-every 7 '
            f'--thermo table --thermo-table "{thermo_table_path}" '
            f'--logs-dir "{logs_dir}"'
        ),
    )

    assert spec.run_name == "CLI Run"
    assert spec.excel_path == excel_path.resolve()
    assert spec.logs_dir == logs_dir.resolve()
    assert spec.n_steps == 42
    assert spec.dt_sec == 0.5
    assert spec.log_every_n_steps == 7
    assert spec.thermo_mode == "table"
    assert spec.thermo_table_path == thermo_table_path.resolve()
    assert "--allow-repeat-command" in spec.command


def test_build_launch_spec_from_cli_reads_dwsim_property_package(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 10,
            "n_components": 2,
            "dt_sec": 0.5,
            "log_every_n_steps": 10,
            "t_final_sec": 300.0,
            "n_steps": 600,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    spec = build_launch_spec_from_cli(
        f'--excel "{excel_path}" --thermo dwsim --dwsim-property-package unifac',
    )

    assert spec.thermo_mode == "dwsim"
    assert spec.dwsim_property_package == "unifac"
    assert "--dwsim-property-package" in spec.command
    assert spec.command[spec.command.index("--dwsim-property-package") + 1] == "unifac"


def test_build_launch_spec_from_cli_infers_restart_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.25,
            "log_every_n_steps": 10,
            "t_final_sec": 60.0,
            "n_steps": 240,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    checkpoint_path = tmp_path / "checkpoint.npz"
    _write_native_checkpoint(checkpoint_path)

    spec = build_launch_spec_from_cli(
        f'--excel "{excel_path}" --init-from-checkpoint "{checkpoint_path}"',
    )

    assert spec.initialization_mode == "restart"
    assert spec.checkpoint_path == checkpoint_path.resolve()
    assert spec.checkpoint_schema == "dynamic_distillation.native_checkpoint.v1"


def test_build_launch_spec_from_cli_injects_selected_restart_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.25,
            "log_every_n_steps": 10,
            "t_final_sec": 60.0,
            "n_steps": 240,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    checkpoint_path = tmp_path / "checkpoint.npz"
    _write_native_checkpoint(checkpoint_path)

    spec = build_launch_spec_from_cli(
        "--runtime-mode hydraulic",
        default_excel_path=excel_path,
        initialization_mode="restart",
        default_checkpoint_path=checkpoint_path,
    )

    assert spec.initialization_mode == "restart"
    assert spec.checkpoint_path == checkpoint_path.resolve()
    assert "--init-from-checkpoint" in spec.command
    assert spec.command[spec.command.index("--init-from-checkpoint") + 1] == str(checkpoint_path.resolve())


def test_build_launch_spec_from_cli_explains_core_v3_research_command() -> None:
    with pytest.raises(ValueError, match="single-use Core V3 DD research command"):
        build_launch_spec_from_cli(
            r"python .\tools\run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory.py --execute"
        )


def test_build_launch_spec_from_cli_accepts_reusable_core_v3_runner(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 60.0,
            "n_steps": 300,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    checkpoint_path = tmp_path / "core_v3.npz"
    _write_core_v3_checkpoint(checkpoint_path)

    spec = build_launch_spec_from_cli(
        "python tools/run_core_v3_dynamic.py --duration-sec 5 --log-every 2",
        default_excel_path=excel_path,
        initialization_mode="restart",
        default_checkpoint_path=checkpoint_path,
    )

    assert spec.checkpoint_schema == "dynamic_distillation.core_v3_checkpoint.v1"
    assert Path(spec.command[2]).name == "run_core_v3_dynamic.py"
    assert spec.n_steps == 20
    assert spec.command[spec.command.index("--parallel-workers") + 1] == "8"


def test_build_launch_spec_from_cli_ignores_windows_caret_continuations(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    spec = build_launch_spec_from_cli(
        (
            f'python -m dynamic_distillation.dynamic_run_scaffold_v1 ^\n'
            f'  --excel "{excel_path}" ^\n'
            f'  --runtime-mode hydraulic ^\n'
            f'  --include-energy'
        ),
    )

    assert "^" not in spec.command
    assert spec.excel_path == excel_path.resolve()
    assert spec.runtime_mode == "hydraulic"
    assert spec.include_energy_override is True


def test_build_launch_spec_from_cli_rejects_log_disabling(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    with pytest.raises(ValueError, match="requires logging"):
        build_launch_spec_from_cli(
            "--no-logs --runtime-mode hydraulic",
            default_excel_path=excel_path,
        )


def test_build_launch_spec_from_cli_rejects_single_dash_long_flag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    with pytest.raises(ValueError, match=r"Unknown runner flag: -top-pressure-ti"):
        build_launch_spec_from_cli(
            f'--excel "{excel_path}" -top-pressure-ti 120 --runtime-mode hydraulic',
        )


def test_build_launch_spec_from_cli_rejects_unknown_double_dash_flag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ui.run_manager.infer_simulation_settings",
        lambda excel_path: {
            "n_stages": 20,
            "n_components": 3,
            "dt_sec": 0.2,
            "log_every_n_steps": 5,
            "t_final_sec": 600.0,
            "n_steps": 3000,
        },
    )
    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")

    with pytest.raises(ValueError, match=r"Unknown runner flag: --not-a-real-flag"):
        build_launch_spec_from_cli(
            f'--excel "{excel_path}" --not-a-real-flag 1 --runtime-mode hydraulic',
        )


def test_build_launch_spec_from_cli_requires_excel_without_ui_default() -> None:
    with pytest.raises(ValueError, match="select/upload a workbook"):
        build_launch_spec_from_cli("--runtime-mode hydraulic")


def test_is_pid_running_uses_tasklist_on_windows(monkeypatch) -> None:
    monkeypatch.setattr("ui.run_manager.os.name", "nt")

    class _Result:
        def __init__(self, returncode: int, stdout: str) -> None:
            self.returncode = returncode
            self.stdout = stdout

    monkeypatch.setattr(
        "ui.run_manager.subprocess.run",
        lambda *args, **kwargs: _Result(0, "python.exe                 24612 Console                    1     10,000 K"),
    )
    assert is_pid_running(24612) is True

    monkeypatch.setattr(
        "ui.run_manager.subprocess.run",
        lambda *args, **kwargs: _Result(0, "INFO: No tasks are running which match the specified criteria."),
    )
    assert is_pid_running(24612) is False


def test_active_run_status_reports_paused_when_flagged(monkeypatch) -> None:
    monkeypatch.setattr("ui.run_manager.is_pid_running", lambda pid: True)
    status = active_run_status({"pid": 1234, "paused": True})
    assert status["is_running"] is True
    assert status["is_paused"] is True
    assert status["status"] == "paused"


def test_active_run_status_prefers_terminal_run_metadata_over_pid_reuse(monkeypatch, tmp_path: Path) -> None:
    logs_dir = tmp_path / "ui_run"
    logs_dir.mkdir()
    (logs_dir / "run_metadata_20260329_162709.json").write_text(
        (
            "{\n"
            '  "status": "completed",\n'
            '  "ended_at_local": "2026-03-29 16:36:05"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("ui.run_manager.is_pid_running", lambda pid: True)

    status = active_run_status(
        {
            "pid": 32980,
            "paused": False,
            "logs_dir": str(logs_dir),
        }
    )

    assert status["is_running"] is False
    assert status["is_paused"] is False
    assert status["status"] == "stopped"


def test_active_run_status_uses_completed_core_v3_horizon(monkeypatch, tmp_path: Path) -> None:
    logs_dir = tmp_path / "ui_run"
    logs_dir.mkdir()
    (logs_dir / "run_metadata_20260820_210000.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "n_steps": 240,
                "dt_sec": 0.25,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("ui.run_manager.is_pid_running", lambda pid: False)

    status = active_run_status(
        {
            "pid": 1234,
            "logs_dir": str(logs_dir),
            "n_steps": 560,
            "dt_sec": 0.25,
        }
    )

    assert status["n_steps"] == 240
    assert status["dt_sec"] == pytest.approx(0.25)


def test_active_run_status_ignores_stale_terminal_metadata_for_new_launch(monkeypatch, tmp_path: Path) -> None:
    logs_dir = tmp_path / "ui_run"
    logs_dir.mkdir()
    (logs_dir / "run_metadata_20260329_162709.json").write_text(
        (
            "{\n"
            '  "status": "completed",\n'
            '  "started_at_local": "2026-03-29 16:27:09",\n'
            '  "ended_at_local": "2026-03-29 16:36:05"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("ui.run_manager.is_pid_running", lambda pid: True)

    status = active_run_status(
        {
            "pid": 32980,
            "paused": False,
            "logs_dir": str(logs_dir),
            "started_at_local": "2026-03-29 17:10:00",
        }
    )

    assert status["is_running"] is True
    assert status["is_paused"] is False
    assert status["status"] == "running"


def test_launch_simulation_injects_src_into_pythonpath(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class _FakeProc:
        def __init__(self) -> None:
            self.pid = 4242

    def _fake_popen(*args, **kwargs):
        captured["env"] = dict(kwargs.get("env") or {})
        return _FakeProc()

    monkeypatch.setattr("ui.run_manager.infer_simulation_settings", lambda excel_path: {
        "n_stages": 20,
        "n_components": 3,
        "dt_sec": 0.2,
        "log_every_n_steps": 10,
        "t_final_sec": 120.0,
        "n_steps": 600,
    })

    excel_path = tmp_path / "case.xlsx"
    excel_path.write_bytes(b"placeholder")
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr("ui.run_manager.UI_STATE_DIR", tmp_path / "ui_state")
    monkeypatch.setattr("ui.run_manager.ACTIVE_RUN_PATH", tmp_path / "ui_state" / "active_run.json")
    monkeypatch.setattr("ui.run_manager.UPLOADS_DIR", tmp_path / "ui_state" / "uploads")
    spec = build_launch_spec(
        excel_path=excel_path,
        run_name="Env Test",
        run_description="",
        logs_dir=logs_dir,
    )
    monkeypatch.setattr("ui.run_manager.subprocess.Popen", _fake_popen)

    launch_simulation(spec)

    assert "PYTHONPATH" in captured["env"]
    assert str((ROOT / "src").resolve()) in captured["env"]["PYTHONPATH"]
    assert captured["env"]["PYTHONUNBUFFERED"] == "1"


def test_request_runtime_extension_writes_control_file(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    path = request_runtime_extension(logs_dir=logs_dir, requested_total_steps=345, dt_sec=0.2)
    assert path == runtime_control_path(logs_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["requested_total_steps"] == 345
    assert payload["requested_total_sim_time_sec"] == pytest.approx(69.0)
    assert payload["source"] == "ui"
