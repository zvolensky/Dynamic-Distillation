from __future__ import annotations

import json
import sys
from pathlib import Path

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
