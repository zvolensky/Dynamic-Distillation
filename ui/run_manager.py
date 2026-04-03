from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_STATE_DIR = PROJECT_ROOT / ".ui_state"
ACTIVE_RUN_PATH = UI_STATE_DIR / "active_run.json"
UPLOADS_DIR = UI_STATE_DIR / "uploads"
DEFAULT_UI_LOGS_DIR = PROJECT_ROOT / "logs" / "ui_runs"
RUNTIME_CONTROL_NAME = "runtime_control.json"
RUNNER_MODULE = "dynamic_distillation.dynamic_run_scaffold_v1"
SRC_DIR = PROJECT_ROOT / "src"


@dataclass(frozen=True)
class SimulationLaunchSpec:
    excel_path: Path
    run_name: str
    run_description: str
    logs_dir: Path
    n_steps: int
    dt_sec: float
    log_every_n_steps: int
    runtime_mode: Optional[str]
    thermo_mode: Optional[str]
    dwsim_property_package: Optional[str]
    thermo_table_path: Optional[Path]
    thermo_table_anchor_blend_count: Optional[int]
    thermo_pool_workers: Optional[int]
    thermo_pool_chunk_size: Optional[int]
    thermo_every_n_steps: Optional[int]
    fast_startup_override: Optional[bool]
    equilibrium_relaxation_live_pr_override: Optional[bool]
    include_energy_override: Optional[bool]
    integrator: Optional[str]
    command: List[str]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_runner_env() -> Dict[str, str]:
    env = dict(os.environ)
    existing = str(env.get("PYTHONPATH", "") or "").strip()
    src_txt = str(SRC_DIR)
    if existing:
        entries = existing.split(os.pathsep)
        if src_txt not in entries:
            env["PYTHONPATH"] = os.pathsep.join([src_txt, *entries])
    else:
        env["PYTHONPATH"] = src_txt
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _slugify(text: str, *, fallback: str = "run") -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", str(text or "").strip()).strip("-").lower()
    return base[:60] if base else fallback


def discover_excel_files(project_root: Path = PROJECT_ROOT) -> List[Path]:
    candidates = []
    for pattern in ("*.xlsx", "sandbox/mini8/input/*.xlsx"):
        candidates.extend(project_root.glob(pattern))
    out = []
    seen = set()
    for path in sorted(candidates):
        try:
            rp = path.resolve()
        except Exception:
            rp = path
        if rp in seen:
            continue
        seen.add(rp)
        out.append(rp)
    return out


def save_uploaded_excel_bytes(name: str, payload: bytes, *, uploads_dir: Path = UPLOADS_DIR) -> Path:
    _ensure_dir(uploads_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = Path(name or "uploaded.xlsx").name
    out = uploads_dir / f"{stamp}_{safe_name}"
    out.write_bytes(payload)
    return out


def infer_simulation_settings(excel_path: Path) -> Dict[str, Any]:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    dt_sec = float(col.sim.dt_sec)
    log_every_n_steps = int(col.sim.log_every_n_steps)
    n_steps = max(int(round(float(col.sim.t_final_sec) / max(dt_sec, 1e-12))), 1)
    return {
        "n_stages": int(col.n_stages),
        "n_components": int(col.n_components),
        "dt_sec": dt_sec,
        "log_every_n_steps": log_every_n_steps,
        "t_final_sec": float(col.sim.t_final_sec),
        "n_steps": n_steps,
    }


def make_run_directory(run_name: str, *, root_logs_dir: Path = DEFAULT_UI_LOGS_DIR) -> Path:
    _ensure_dir(root_logs_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(run_name, fallback="ui-run")
    return root_logs_dir / f"{stamp}_{slug}"


def _dequote_token(token: str) -> str:
    text = str(token or "")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _tokenize_cli_text(command_text: str) -> List[str]:
    normalized = str(command_text or "").strip()
    normalized = re.sub(r"\^\s*\r?\n\s*", " ", normalized)
    normalized = re.sub(r"[`\\]\s*\r?\n\s*", " ", normalized)
    if not normalized:
        raise ValueError("Enter a CLI command or runner flags.")
    try:
        tokens = shlex.split(normalized, posix=False)
    except ValueError as exc:
        raise ValueError(f"Could not parse CLI text: {exc}") from exc
    out = []
    for tok in tokens:
        txt = _dequote_token(tok).strip()
        if not txt or txt in {"^", "-"}:
            continue
        out.append(txt)
    if not out:
        raise ValueError("Enter a CLI command or runner flags.")
    return out


def _looks_like_python_invocation(token: str) -> bool:
    base = Path(str(token or "")).name.lower()
    return base in {
        "python",
        "python.exe",
        "py",
        "py.exe",
        Path(sys.executable).name.lower(),
    }


def _is_runner_script(token: str) -> bool:
    normalized = str(token or "").replace("\\", "/").strip().lower()
    return normalized.endswith("/dynamic_run_scaffold_v1.py") or normalized == "dynamic_run_scaffold_v1.py"


def _extract_runner_argv(command_text: str) -> List[str]:
    tokens = _tokenize_cli_text(command_text)
    if not tokens:
        raise ValueError("Enter a CLI command or runner flags.")
    if str(tokens[0]).startswith("-"):
        return list(tokens)

    work = list(tokens)
    if _looks_like_python_invocation(work[0]):
        work = work[1:]
        if not work:
            raise ValueError("CLI command is missing the simulation runner or flags.")

    if work[0] == "-m":
        if len(work) < 2 or str(work[1]).strip() != RUNNER_MODULE:
            raise ValueError(f"CLI mode only supports `{RUNNER_MODULE}`.")
        return work[2:]

    if str(work[0]).strip() == RUNNER_MODULE:
        return work[1:]

    if _is_runner_script(work[0]):
        return work[1:]

    raise ValueError(
        "CLI mode accepts either bare runner flags or a command targeting "
        f"`{RUNNER_MODULE}`."
    )


def _find_last_option_value(tokens: List[str], *names: str) -> Optional[str]:
    names_set = set(names)
    value: Optional[str] = None
    for idx, token in enumerate(tokens):
        if token in names_set and idx + 1 < len(tokens):
            value = str(tokens[idx + 1])
    return value


def _has_any_flag(tokens: List[str], *names: str) -> bool:
    names_set = set(names)
    return any(token in names_set for token in tokens)


def _resolve_cli_path(path_text: str) -> Path:
    path = Path(str(path_text))
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def build_launch_spec(
    *,
    excel_path: Path,
    run_name: str,
    run_description: str,
    logs_dir: Optional[Path] = None,
    runtime_mode: Optional[str] = None,
    thermo_mode: Optional[str] = None,
    dwsim_property_package: Optional[str] = None,
    thermo_table_path: Optional[Path] = None,
    thermo_table_anchor_blend_count: Optional[int] = None,
    thermo_pool_workers: Optional[int] = None,
    thermo_pool_chunk_size: Optional[int] = None,
    thermo_every_n_steps: Optional[int] = None,
    fast_startup_override: Optional[bool] = None,
    equilibrium_relaxation_live_pr_override: Optional[bool] = None,
    include_energy_override: Optional[bool] = None,
    integrator: Optional[str] = None,
) -> SimulationLaunchSpec:
    settings = infer_simulation_settings(excel_path)
    run_name_clean = str(run_name or "").strip() or excel_path.stem
    run_description_clean = str(run_description or "").strip()
    run_logs_dir = logs_dir or make_run_directory(run_name_clean)
    effective_thermo_mode = str(thermo_mode or "table-pool")
    effective_dwsim_package = str(dwsim_property_package or "pr")
    effective_thermo_table_path = (
        Path(thermo_table_path) if (thermo_table_path and effective_thermo_mode in {"table", "table-pool"}) else None
    )
    command = [
        sys.executable,
        "-u",
        "-m",
        "dynamic_distillation.dynamic_run_scaffold_v1",
        "--excel",
        str(excel_path),
        "--n-steps",
        str(int(settings["n_steps"])),
        "--dt",
        str(float(settings["dt_sec"])),
        "--log-every",
        str(int(settings["log_every_n_steps"])),
        "--logs-dir",
        str(run_logs_dir),
        "--run-name",
        run_name_clean,
        "--allow-repeat-command",
    ]
    if run_description_clean:
        command.extend(["--run-description", run_description_clean])
    if runtime_mode:
        command.extend(["--runtime-mode", str(runtime_mode)])
    command.extend(["--thermo", effective_thermo_mode])
    if effective_thermo_mode == "dwsim":
        command.extend(["--dwsim-property-package", effective_dwsim_package])
    if effective_thermo_table_path:
        command.extend(["--thermo-table", str(effective_thermo_table_path)])
    if thermo_table_anchor_blend_count is not None:
        command.extend(["--thermo-table-anchor-blend-count", str(int(thermo_table_anchor_blend_count))])
    if thermo_pool_workers is not None:
        command.extend(["--thermo-pool-workers", str(int(thermo_pool_workers))])
    if thermo_pool_chunk_size is not None:
        command.extend(["--thermo-pool-chunk-size", str(int(thermo_pool_chunk_size))])
    if thermo_every_n_steps is not None:
        command.extend(["--thermo-every", str(int(thermo_every_n_steps))])
    if fast_startup_override is True:
        command.append("--fast-startup")
    if equilibrium_relaxation_live_pr_override is True:
        command.append("--equilibrium-relaxation-live-pr")
    if include_energy_override is True:
        command.append("--include-energy")
    if integrator:
        command.extend(["--integrator", str(integrator)])
    return SimulationLaunchSpec(
        excel_path=excel_path,
        run_name=run_name_clean,
        run_description=run_description_clean,
        logs_dir=run_logs_dir,
        n_steps=int(settings["n_steps"]),
        dt_sec=float(settings["dt_sec"]),
        log_every_n_steps=int(settings["log_every_n_steps"]),
        runtime_mode=str(runtime_mode) if runtime_mode else None,
        thermo_mode=effective_thermo_mode,
        dwsim_property_package=effective_dwsim_package if effective_thermo_mode == "dwsim" else None,
        thermo_table_path=effective_thermo_table_path,
        thermo_table_anchor_blend_count=(
            int(thermo_table_anchor_blend_count) if thermo_table_anchor_blend_count is not None else None
        ),
        thermo_pool_workers=int(thermo_pool_workers) if thermo_pool_workers is not None else None,
        thermo_pool_chunk_size=int(thermo_pool_chunk_size) if thermo_pool_chunk_size is not None else None,
        thermo_every_n_steps=int(thermo_every_n_steps) if thermo_every_n_steps is not None else None,
        fast_startup_override=fast_startup_override,
        equilibrium_relaxation_live_pr_override=equilibrium_relaxation_live_pr_override,
        include_energy_override=include_energy_override,
        integrator=str(integrator) if integrator else None,
        command=command,
    )


def build_launch_spec_from_cli(
    command_text: str,
    *,
    default_excel_path: Optional[Path] = None,
) -> SimulationLaunchSpec:
    raw_argv = _extract_runner_argv(command_text)
    if _has_any_flag(raw_argv, "--no-write-logs", "--no-logs"):
        raise ValueError("CLI mode in the UI requires logging to stay enabled.")

    excel_arg = _find_last_option_value(raw_argv, "--excel")
    if excel_arg:
        excel_path = _resolve_cli_path(excel_arg)
    elif default_excel_path is not None:
        excel_path = Path(default_excel_path).resolve()
    else:
        raise ValueError("Add `--excel ...` to the CLI or select/upload a workbook in the UI first.")
    if not excel_path.exists():
        raise ValueError(f"Excel path does not exist: {excel_path}")

    settings = infer_simulation_settings(excel_path)
    run_name = str(_find_last_option_value(raw_argv, "--run-name") or excel_path.stem).strip() or excel_path.stem
    run_description = str(_find_last_option_value(raw_argv, "--run-description") or "").strip()

    logs_dir_arg = _find_last_option_value(raw_argv, "--logs-dir")
    logs_dir = _resolve_cli_path(logs_dir_arg) if logs_dir_arg else make_run_directory(run_name)

    normalized_argv = list(raw_argv)
    if not excel_arg:
        normalized_argv = ["--excel", str(excel_path)] + normalized_argv
    if not logs_dir_arg:
        normalized_argv.extend(["--logs-dir", str(logs_dir)])
    if not _has_any_flag(normalized_argv, "--allow-repeat-command"):
        normalized_argv.append("--allow-repeat-command")

    n_steps_text = _find_last_option_value(normalized_argv, "--n-steps", "--steps")
    dt_text = _find_last_option_value(normalized_argv, "--dt")
    log_every_text = _find_last_option_value(normalized_argv, "--log-every")
    thermo_table_text = _find_last_option_value(normalized_argv, "--thermo-table")
    thermo_anchor_blend_text = _find_last_option_value(normalized_argv, "--thermo-table-anchor-blend-count")
    thermo_pool_workers_text = _find_last_option_value(normalized_argv, "--thermo-pool-workers")
    thermo_pool_chunk_text = _find_last_option_value(normalized_argv, "--thermo-pool-chunk-size")
    thermo_every_text = _find_last_option_value(normalized_argv, "--thermo-every")
    dwsim_property_package = _find_last_option_value(normalized_argv, "--dwsim-property-package")
    integrator = _find_last_option_value(normalized_argv, "--integrator") or "explicit-euler"
    runtime_mode = _find_last_option_value(normalized_argv, "--runtime-mode") or "parity"
    thermo_mode = _find_last_option_value(normalized_argv, "--thermo") or "table-pool"

    try:
        n_steps = int(float(n_steps_text)) if n_steps_text is not None else 600
    except Exception as exc:
        raise ValueError(f"Invalid `--n-steps/--steps` value: {n_steps_text}") from exc
    try:
        dt_sec = float(dt_text) if dt_text is not None else float(settings["dt_sec"])
    except Exception as exc:
        raise ValueError(f"Invalid `--dt` value: {dt_text}") from exc
    try:
        log_every_n_steps = (
            int(float(log_every_text)) if log_every_text is not None else int(settings["log_every_n_steps"])
        )
    except Exception as exc:
        raise ValueError(f"Invalid `--log-every` value: {log_every_text}") from exc

    def _maybe_int(value: Optional[str], *, default: Optional[int] = None, flag_name: str) -> Optional[int]:
        if value is None:
            return default
        try:
            return int(float(value))
        except Exception as exc:
            raise ValueError(f"Invalid `{flag_name}` value: {value}") from exc

    thermo_table_path = _resolve_cli_path(thermo_table_text) if thermo_table_text else None

    return SimulationLaunchSpec(
        excel_path=excel_path,
        run_name=run_name,
        run_description=run_description,
        logs_dir=logs_dir,
        n_steps=n_steps,
        dt_sec=dt_sec,
        log_every_n_steps=log_every_n_steps,
        runtime_mode=runtime_mode,
        thermo_mode=thermo_mode,
        dwsim_property_package=dwsim_property_package if thermo_mode == "dwsim" else None,
        thermo_table_path=thermo_table_path,
        thermo_table_anchor_blend_count=_maybe_int(
            thermo_anchor_blend_text,
            default=3,
            flag_name="--thermo-table-anchor-blend-count",
        ),
        thermo_pool_workers=_maybe_int(
            thermo_pool_workers_text,
            default=2,
            flag_name="--thermo-pool-workers",
        ),
        thermo_pool_chunk_size=_maybe_int(
            thermo_pool_chunk_text,
            default=4,
            flag_name="--thermo-pool-chunk-size",
        ),
        thermo_every_n_steps=_maybe_int(
            thermo_every_text,
            default=1,
            flag_name="--thermo-every",
        ),
        fast_startup_override=_has_any_flag(normalized_argv, "--fast-startup"),
        equilibrium_relaxation_live_pr_override=_has_any_flag(
            normalized_argv,
            "--equilibrium-relaxation-live-pr",
        ),
        include_energy_override=_has_any_flag(normalized_argv, "--include-energy", "--energy"),
        integrator=integrator,
        command=[sys.executable, "-u", "-m", RUNNER_MODULE, *normalized_argv],
    )


def _write_active_run(payload: Dict[str, Any]) -> None:
    _ensure_dir(UI_STATE_DIR)
    ACTIVE_RUN_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def runtime_control_path(logs_dir: Path) -> Path:
    return Path(logs_dir) / RUNTIME_CONTROL_NAME


def request_runtime_extension(*, logs_dir: Path, requested_total_steps: int, dt_sec: float) -> Path:
    _ensure_dir(Path(logs_dir))
    payload = {
        "requested_total_steps": int(max(int(requested_total_steps), 1)),
        "requested_total_sim_time_sec": float(max(float(requested_total_steps) * float(dt_sec), 0.0)),
        "dt_sec": float(dt_sec),
        "updated_at_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ui",
    }
    path = runtime_control_path(Path(logs_dir))
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def _read_latest_run_metadata(logs_dir: Optional[Path]) -> Dict[str, Any]:
    if logs_dir is None:
        return {}
    try:
        matches = sorted(Path(logs_dir).glob("run_metadata_*.json"))
    except Exception:
        return {}
    if not matches:
        return {}
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_local_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def update_active_run(**fields: Any) -> Optional[Dict[str, Any]]:
    payload = read_active_run()
    if not payload:
        return None
    payload.update(fields)
    _write_active_run(payload)
    return payload


def read_active_run() -> Optional[Dict[str, Any]]:
    if not ACTIVE_RUN_PATH.exists():
        return None
    try:
        return json.loads(ACTIVE_RUN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_active_run() -> None:
    if ACTIVE_RUN_PATH.exists():
        ACTIVE_RUN_PATH.unlink()


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
            )
            if proc.returncode != 0:
                return False
            out = str(proc.stdout or "")
            return str(pid) in out and "No tasks are running" not in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _nt_process_control(pid: int, function_name: str) -> bool:
    if os.name != "nt" or pid <= 0:
        return False
    try:
        import ctypes

        PROCESS_SUSPEND_RESUME = 0x0800
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        open_process.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        proc_handle = open_process(PROCESS_SUSPEND_RESUME, 0, int(pid))
        if not proc_handle:
            return False
        try:
            control_fn = getattr(ntdll, function_name)
            control_fn.argtypes = [ctypes.c_void_p]
            control_fn.restype = ctypes.c_ulong
            status = int(control_fn(proc_handle))
            return status == 0
        finally:
            close_handle(proc_handle)
    except Exception:
        return False


def suspend_pid(pid: int) -> bool:
    return _nt_process_control(pid, "NtSuspendProcess")


def resume_pid(pid: int) -> bool:
    return _nt_process_control(pid, "NtResumeProcess")


def terminate_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        return proc.returncode == 0
    try:
        os.kill(pid, 15)
        return True
    except Exception:
        return False


def launch_simulation(spec: SimulationLaunchSpec) -> Dict[str, Any]:
    _ensure_dir(spec.logs_dir)
    stdout_path = spec.logs_dir / "runner_stdout.log"
    stderr_path = spec.logs_dir / "runner_stderr.log"
    stdout_file = stdout_path.open("w", encoding="utf-8")
    stderr_file = stderr_path.open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            spec.command,
            cwd=str(PROJECT_ROOT),
            env=_build_runner_env(),
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
        )
    except Exception:
        stdout_file.close()
        stderr_file.close()
        raise

    payload = {
        "pid": int(proc.pid),
        "run_name": spec.run_name,
        "run_description": spec.run_description,
        "excel_path": str(spec.excel_path),
        "logs_dir": str(spec.logs_dir),
        "runtime_control_json": str(runtime_control_path(spec.logs_dir)),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "started_at_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "paused": False,
        "command": list(spec.command),
        "n_steps": int(spec.n_steps),
        "dt_sec": float(spec.dt_sec),
        "log_every_n_steps": int(spec.log_every_n_steps),
    }
    _write_active_run(payload)
    stdout_file.close()
    stderr_file.close()
    return payload


def active_run_status(active_run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not active_run:
        return {"status": "idle", "is_running": False}
    logs_dir = Path(str(active_run.get("logs_dir"))) if active_run.get("logs_dir") else None
    run_metadata = _read_latest_run_metadata(logs_dir)
    terminal_statuses = {"completed", "failed", "error", "aborted", "stopped", "terminated"}
    if run_metadata:
        status_txt = str(run_metadata.get("status", "") or "").strip().lower()
        ended_at = str(run_metadata.get("ended_at_local", "") or "").strip()
        active_started_dt = _parse_local_timestamp(active_run.get("started_at_local"))
        meta_started_dt = _parse_local_timestamp(run_metadata.get("started_at_local"))
        meta_ended_dt = _parse_local_timestamp(run_metadata.get("ended_at_local"))
        metadata_is_stale = False
        if active_started_dt is not None:
            if meta_started_dt is not None and meta_started_dt < active_started_dt:
                if meta_ended_dt is None or meta_ended_dt < active_started_dt:
                    metadata_is_stale = True
            elif meta_started_dt is None and meta_ended_dt is not None and meta_ended_dt < active_started_dt:
                metadata_is_stale = True
        if (status_txt in terminal_statuses or ended_at) and not metadata_is_stale:
            out = dict(active_run)
            out["is_running"] = False
            out["is_paused"] = False
            out["status"] = "stopped"
            return out
    pid = int(active_run.get("pid") or 0)
    is_running = is_pid_running(pid)
    is_paused = bool(is_running and active_run.get("paused", False))
    status = "paused" if is_paused else ("running" if is_running else "stopped")
    out = dict(active_run)
    out["is_running"] = bool(is_running)
    out["is_paused"] = bool(is_paused)
    out["status"] = status
    return out


def archive_uploaded_file(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    archived = path.with_name(path.stem + "_archived" + path.suffix)
    shutil.move(str(path), str(archived))
    return archived
