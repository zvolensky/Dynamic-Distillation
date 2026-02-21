"""
experiment_ledger_v1.py

Dynamic Distillation - Run Registry and Ledger Management

PURPOSE
-------
Track run provenance and command identity, append run metadata, and regenerate
human-readable and CSV experiment ledgers from run artifacts.

INPUTS
------
- module name + argv command context
- run summary/profile CSV paths
- project/log directory paths

OUTPUTS
-------
- appended/updated `logs/run_registry.csv`
- regenerated `docs/experiment_ledger.csv`
- regenerated `docs/experiment_ledger.md`
- exact-command match records for duplicate guard logic

KEY DEPENDENCIES
----------------
- csv/pathlib utilities
- runner-produced summary/profile schemas

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Command identity normalization intentionally ignores guard-only flags.
- Ledger regeneration tolerates partial/missing artifacts where possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import csv
import json
import re
from collections import defaultdict
import numpy as np


_RUN_ID_RE = re.compile(r"column_summary_(\d{8}_\d{6})\.csv$")
_FEAS_ID_RE = re.compile(r"feasibility_trim_search_(\d{8}_\d{6})\.csv$")
_NON_EXPERIMENT_FLAGS = {"--allow-repeat-command"}


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    run_datetime_local: str
    status: str
    command_source: str
    cli_command: str
    summary_csv: str
    profile_csv: str
    t_final_s: str
    P_top_pv_psia_final: str
    P_top_sp_psia_final: str
    xD_pv_final: str
    xD_sp_final: str
    xB_pv_final: str
    xB_sp_final: str
    Reflux_cmd_lbmolph_final: str
    Boilup_cmd_lbmolph_final: str
    D_lbmolph_final: str
    B_lbmolph_final: str
    TopL_init_lbmol: str
    TopL_final_lbmol: str
    BotL_init_lbmol: str
    BotL_final_lbmol: str
    global_mass_closure_error_final_lbmolph: str
    global_mass_closure_error_abs_max_lbmolph: str
    exact_command_dup_group: str
    exact_command_dup_count: str
    suspected_dup_group: str
    suspected_dup_count: str
    suspected_duplicate: str


@dataclass(frozen=True)
class CommandMatch:
    run_id: str
    run_datetime_local: str
    status: str
    command_source: str
    t_final_s: str
    P_top_pv_psia_final: str
    xD_pv_final: str
    xB_pv_final: str
    summary_csv: str


def _safe_float_text(x: object) -> str:
    try:
        v = float(x)  # type: ignore[arg-type]
    except Exception:
        return ""
    if not (v == v) or v in (float("inf"), float("-inf")):
        return ""
    return repr(v)


def _fmt_float_text(x: str, nd: int = 6) -> str:
    if not x:
        return ""
    try:
        v = float(x)
    except Exception:
        return x
    av = abs(v)
    if av >= 1e5 or (0.0 < av < 1e-4):
        return f"{v:.3e}"
    return f"{v:.{nd}f}"


def _quote_arg(arg: str) -> str:
    if arg == "":
        return '""'
    needs_quotes = any(ch.isspace() for ch in arg) or ('"' in arg) or ("'" in arg)
    if not needs_quotes:
        return arg
    return '"' + arg.replace('"', '\\"') + '"'


def _compose_command(module_name: str, argv: Sequence[str]) -> str:
    rendered = " ".join(_quote_arg(a) for a in argv)
    module_txt = str(module_name or "").strip()
    if module_txt.endswith(".py") or ("/" in module_txt) or ("\\" in module_txt):
        if rendered:
            return f"python {module_txt} {rendered}"
        return f"python {module_txt}"
    if rendered:
        return f"python -m {module_txt} {rendered}"
    return f"python -m {module_txt}"


def compose_cli_command(module_name: str, argv: Sequence[str]) -> str:
    """Public helper to render the canonical command string used in ledger rows."""
    return _compose_command(module_name, argv)


def _normalize_command_for_identity(command_text: str) -> str:
    s = str(command_text or "")
    for flag in _NON_EXPERIMENT_FLAGS:
        s = re.sub(rf"(?:(?<=\s)|^){re.escape(flag)}(?=\s|$)", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compose_cli_command_identity(module_name: str, argv: Sequence[str]) -> str:
    """
    Render command identity used for duplicate checks.

    Non-experiment flags (override/metadata flags) are removed.
    """
    argv_eff = [a for a in argv if str(a) not in _NON_EXPERIMENT_FLAGS]
    return _normalize_command_for_identity(_compose_command(module_name, argv_eff))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path.resolve()).replace("\\", "/")


def _read_existing_command_map(ledger_csv_path: Path) -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    if not ledger_csv_path.exists() or ledger_csv_path.stat().st_size == 0:
        return out
    try:
        with ledger_csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                run_id = str(row.get("run_id") or "").strip()
                src = str(row.get("command_source") or "").strip()
                cmd = str(row.get("cli_command") or "")
                if not run_id or not cmd:
                    continue
                if src.lower() == "unknown":
                    continue
                out[run_id] = (src, cmd)
    except Exception:
        return out
    return out


def _read_registry_command_map(registry_csv_path: Path) -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    if not registry_csv_path.exists() or registry_csv_path.stat().st_size == 0:
        return out
    try:
        with registry_csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                run_id = str(row.get("run_id") or "").strip()
                src = str(row.get("command_source") or "").strip()
                cmd = str(row.get("cli_command") or "")
                if not run_id or not cmd:
                    continue
                if src.lower() == "unknown":
                    continue
                out[run_id] = (src, cmd)
    except Exception:
        return out
    return out


def _read_summary_first_last(summary_csv_path: Path) -> Tuple[Optional[dict], Optional[dict], str]:
    if not summary_csv_path.exists():
        return None, None, "missing-summary"
    if summary_csv_path.stat().st_size == 0:
        return None, None, "empty-summary"
    first = None
    last = None
    try:
        with summary_csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                if first is None:
                    first = row
                last = row
    except Exception:
        return None, None, "read-error"
    if first is None or last is None:
        return None, None, "empty-summary"
    return first, last, "ok"


def _mass_error_abs_max(summary_csv_path: Path) -> str:
    try:
        max_abs = 0.0
        seen = False
        with summary_csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                s = row.get("global_mass_closure_error_lbmolph")
                try:
                    v = float(s)  # type: ignore[arg-type]
                except Exception:
                    continue
                if not (v == v) or v in (float("inf"), float("-inf")):
                    continue
                seen = True
                av = abs(v)
                if av > max_abs:
                    max_abs = av
        if not seen:
            return ""
        return repr(max_abs)
    except Exception:
        return ""


def _choose_p_top(last: dict) -> str:
    for key in ("P_top_drum_psia", "P_top_ctrl_pv_psia", "P_top_psia"):
        if key in last:
            txt = _safe_float_text(last.get(key))
            if txt:
                return txt
    return ""


def _iter_summary_files(logs_dir: Path) -> Iterable[Tuple[str, Path]]:
    for path in sorted(logs_dir.glob("column_summary_*.csv")):
        m = _RUN_ID_RE.match(path.name)
        if not m:
            continue
        yield m.group(1), path


def _iter_feasibility_files(logs_dir: Path) -> Iterable[Tuple[str, Path]]:
    for path in sorted(logs_dir.glob("feasibility_trim_search_*.csv")):
        m = _FEAS_ID_RE.match(path.name)
        if not m:
            continue
        yield m.group(1), path


def _run_id_from_results_filename(path: Path) -> Optional[str]:
    name = path.name
    m = _RUN_ID_RE.match(name)
    if m:
        return m.group(1)
    m = _FEAS_ID_RE.match(name)
    if m:
        return m.group(1)
    return None


def _read_feasibility_best(feas_csv_path: Path) -> Tuple[Optional[dict], str]:
    if not feas_csv_path.exists():
        return None, "missing-summary"
    if feas_csv_path.stat().st_size == 0:
        return None, "empty-summary"

    rows: List[dict] = []
    try:
        with feas_csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append(row)
    except Exception:
        return None, "read-error"
    if not rows:
        return None, "empty-summary"

    ok_rows: List[dict] = []
    for row in rows:
        ok_flag = str(row.get("ok") or "").strip().lower()
        if ok_flag in ("1", "true", "yes", "y"):
            ok_rows.append(row)
    cand = ok_rows if ok_rows else rows

    def _score(row: dict) -> float:
        try:
            v = float(row.get("score"))
        except Exception:
            return float("inf")
        if not np.isfinite(v):
            return float("inf")
        return float(v)

    best = min(cand, key=_score)
    return best, "ok"


def find_exact_command_matches(
    *,
    ledger_csv_path: Path,
    module_name: str,
    argv: Sequence[str],
) -> List[CommandMatch]:
    """
    Return rows whose stored CLI command exactly matches this candidate command.
    """
    if not ledger_csv_path.exists() or ledger_csv_path.stat().st_size == 0:
        return []
    candidate = compose_cli_command_identity(module_name, argv)
    out: List[CommandMatch] = []
    try:
        with ledger_csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                cmd = str(row.get("cli_command") or "")
                if not cmd:
                    continue
                cmd_identity = _normalize_command_for_identity(cmd)
                if cmd_identity != candidate:
                    continue
                out.append(
                    CommandMatch(
                        run_id=str(row.get("run_id") or ""),
                        run_datetime_local=str(row.get("run_datetime_local") or ""),
                        status=str(row.get("status") or ""),
                        command_source=str(row.get("command_source") or ""),
                        t_final_s=str(row.get("t_final_s") or ""),
                        P_top_pv_psia_final=str(row.get("P_top_pv_psia_final") or ""),
                        xD_pv_final=str(row.get("xD_pv_final") or ""),
                        xB_pv_final=str(row.get("xB_pv_final") or ""),
                        summary_csv=str(row.get("summary_csv") or ""),
                    )
                )
    except Exception:
        return []
    out.sort(key=lambda x: x.run_id, reverse=True)
    return out


def _run_result_signature_key(r: RunRecord) -> Tuple[str, ...]:
    """
    Signature used for suspected duplicate detection on run outcomes.

    This compares final-state outcomes, not command text, and is intended as a
    heuristic for old runs where CLI command was not captured.
    """
    return (
        r.status,
        r.t_final_s,
        r.P_top_pv_psia_final,
        r.P_top_sp_psia_final,
        r.xD_pv_final,
        r.xD_sp_final,
        r.xB_pv_final,
        r.xB_sp_final,
        r.Reflux_cmd_lbmolph_final,
        r.Boilup_cmd_lbmolph_final,
        r.D_lbmolph_final,
        r.B_lbmolph_final,
        r.TopL_init_lbmol,
        r.TopL_final_lbmol,
        r.BotL_init_lbmol,
        r.BotL_final_lbmol,
        r.global_mass_closure_error_final_lbmolph,
        r.global_mass_closure_error_abs_max_lbmolph,
    )


def _run_result_signature_strength(r: RunRecord) -> int:
    key = _run_result_signature_key(r)
    if not key:
        return 0
    # Ignore status element for strength count.
    return sum(1 for v in key[1:] if str(v).strip() != "")


def _compute_exact_command_duplicates(
    rows: Sequence[RunRecord],
) -> Tuple[Dict[str, str], Dict[str, int], List[Tuple[str, int, List[str]]]]:
    by_cmd: Dict[str, List[RunRecord]] = defaultdict(list)
    for r in rows:
        cmd = str(r.cli_command or "").strip()
        if not cmd:
            continue
        by_cmd[cmd].append(r)

    groups = [g for g in by_cmd.values() if len(g) > 1]
    groups.sort(key=lambda g: (max(x.run_id for x in g), len(g)), reverse=True)

    run_to_group: Dict[str, str] = {}
    run_to_count: Dict[str, int] = {}
    summary: List[Tuple[str, int, List[str]]] = []
    for i, grp in enumerate(groups, start=1):
        gid = f"CMDDUP{i:03d}"
        run_ids = sorted((r.run_id for r in grp), reverse=True)
        for r in grp:
            run_to_group[r.run_id] = gid
            run_to_count[r.run_id] = len(grp)
        summary.append((gid, len(grp), run_ids))
    return run_to_group, run_to_count, summary


def _compute_suspected_duplicates(
    rows: Sequence[RunRecord],
) -> Tuple[Dict[str, str], Dict[str, int], List[Tuple[str, int, List[str]]]]:
    by_sig: Dict[Tuple[str, ...], List[RunRecord]] = defaultdict(list)
    for r in rows:
        if str(r.status).lower() != "ok":
            continue
        if _run_result_signature_strength(r) < 8:
            continue
        by_sig[_run_result_signature_key(r)].append(r)

    groups = [g for g in by_sig.values() if len(g) > 1]
    groups.sort(key=lambda g: (max(x.run_id for x in g), len(g)), reverse=True)

    run_to_group: Dict[str, str] = {}
    run_to_count: Dict[str, int] = {}
    summary: List[Tuple[str, int, List[str]]] = []
    for i, grp in enumerate(groups, start=1):
        gid = f"SIGDUP{i:03d}"
        run_ids = sorted((r.run_id for r in grp), reverse=True)
        for r in grp:
            run_to_group[r.run_id] = gid
            run_to_count[r.run_id] = len(grp)
        summary.append((gid, len(grp), run_ids))
    return run_to_group, run_to_count, summary


def _row_to_record(row: dict) -> RunRecord:
    return RunRecord(
        run_id=str(row.get("run_id") or ""),
        run_datetime_local=str(row.get("run_datetime_local") or ""),
        status=str(row.get("status") or ""),
        command_source=str(row.get("command_source") or "unknown"),
        cli_command=str(row.get("cli_command") or ""),
        summary_csv=str(row.get("summary_csv") or ""),
        profile_csv=str(row.get("profile_csv") or ""),
        t_final_s=str(row.get("t_final_s") or ""),
        P_top_pv_psia_final=str(row.get("P_top_pv_psia_final") or ""),
        P_top_sp_psia_final=str(row.get("P_top_sp_psia_final") or ""),
        xD_pv_final=str(row.get("xD_pv_final") or ""),
        xD_sp_final=str(row.get("xD_sp_final") or ""),
        xB_pv_final=str(row.get("xB_pv_final") or ""),
        xB_sp_final=str(row.get("xB_sp_final") or ""),
        Reflux_cmd_lbmolph_final=str(row.get("Reflux_cmd_lbmolph_final") or ""),
        Boilup_cmd_lbmolph_final=str(row.get("Boilup_cmd_lbmolph_final") or ""),
        D_lbmolph_final=str(row.get("D_lbmolph_final") or ""),
        B_lbmolph_final=str(row.get("B_lbmolph_final") or ""),
        TopL_init_lbmol=str(row.get("TopL_init_lbmol") or ""),
        TopL_final_lbmol=str(row.get("TopL_final_lbmol") or ""),
        BotL_init_lbmol=str(row.get("BotL_init_lbmol") or ""),
        BotL_final_lbmol=str(row.get("BotL_final_lbmol") or ""),
        global_mass_closure_error_final_lbmolph=str(row.get("global_mass_closure_error_final_lbmolph") or ""),
        global_mass_closure_error_abs_max_lbmolph=str(row.get("global_mass_closure_error_abs_max_lbmolph") or ""),
        exact_command_dup_group=str(row.get("exact_command_dup_group") or ""),
        exact_command_dup_count=str(row.get("exact_command_dup_count") or ""),
        suspected_dup_group=str(row.get("suspected_dup_group") or ""),
        suspected_dup_count=str(row.get("suspected_dup_count") or ""),
        suspected_duplicate=str(row.get("suspected_duplicate") or "0"),
    )


def append_run_registry_entry(
    *,
    logs_dir: Path,
    module_name: str,
    argv: Sequence[str],
    summary_csv_path: Optional[str],
    profile_csv_path: Optional[str],
) -> None:
    """
    Append an exact command capture row for this run.

    This only records runs that produced a summary CSV with a recognized run_id.
    """
    if not summary_csv_path:
        return
    summary_path = Path(summary_csv_path)
    run_id = _run_id_from_results_filename(summary_path)
    if not run_id:
        return
    try:
        run_dt = datetime.strptime(run_id, "%Y%m%d_%H%M%S")
        run_dt_txt = run_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        run_dt_txt = ""

    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cmd = _compose_command(module_name, argv)

    registry_path = logs_dir / "run_registry.csv"
    logs_dir.mkdir(parents=True, exist_ok=True)

    fields = [
        "run_id",
        "run_datetime_local",
        "recorded_at_local",
        "module_name",
        "command_source",
        "cli_command",
        "argv_json",
        "summary_csv",
        "profile_csv",
    ]

    write_header = (not registry_path.exists()) or registry_path.stat().st_size == 0
    with registry_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerow(
            {
                "run_id": run_id,
                "run_datetime_local": run_dt_txt,
                "recorded_at_local": now_txt,
                "module_name": module_name,
                "command_source": "auto-captured",
                "cli_command": cmd,
                "argv_json": json.dumps(list(argv), ensure_ascii=True),
                "summary_csv": str(summary_path),
                "profile_csv": str(profile_csv_path or ""),
            }
        )


def rebuild_experiment_ledger(
    *,
    project_root: Path,
    logs_dir: Optional[Path] = None,
    docs_dir: Optional[Path] = None,
) -> Tuple[Path, Path, int]:
    """
    Regenerate `docs/experiment_ledger.csv` and `.md`.
    """
    root = project_root.resolve()
    logs = (logs_dir or (root / "logs")).resolve()
    docs = (docs_dir or (root / "docs")).resolve()
    docs.mkdir(parents=True, exist_ok=True)

    ledger_csv = docs / "experiment_ledger.csv"
    ledger_md = docs / "experiment_ledger.md"
    registry_csv = logs / "run_registry.csv"

    existing_cmd_map = _read_existing_command_map(ledger_csv)
    registry_cmd_map = _read_registry_command_map(registry_csv)
    known_cmd_map: Dict[str, Tuple[str, str]] = dict(existing_cmd_map)
    known_cmd_map.update(registry_cmd_map)

    rows: List[RunRecord] = []
    seen_run_ids: set[str] = set()
    for run_id, summary_path in _iter_summary_files(logs):
        run_dt = datetime.strptime(run_id, "%Y%m%d_%H%M%S")
        run_dt_txt = run_dt.strftime("%Y-%m-%d %H:%M:%S")
        profile_path = logs / f"column_profile_{run_id}.csv"

        first, last, status = _read_summary_first_last(summary_path)
        src = "unknown"
        cmd = ""
        if run_id in known_cmd_map:
            src, cmd = known_cmd_map[run_id]

        row = {
            "run_id": run_id,
            "run_datetime_local": run_dt_txt,
            "status": status,
            "command_source": src,
            "cli_command": cmd,
            "summary_csv": _relative_path(summary_path, root),
            "profile_csv": _relative_path(profile_path, root) if profile_path.exists() else "",
            "t_final_s": "",
            "P_top_pv_psia_final": "",
            "P_top_sp_psia_final": "",
            "xD_pv_final": "",
            "xD_sp_final": "",
            "xB_pv_final": "",
            "xB_sp_final": "",
            "Reflux_cmd_lbmolph_final": "",
            "Boilup_cmd_lbmolph_final": "",
            "D_lbmolph_final": "",
            "B_lbmolph_final": "",
            "TopL_init_lbmol": "",
            "TopL_final_lbmol": "",
            "BotL_init_lbmol": "",
            "BotL_final_lbmol": "",
            "global_mass_closure_error_final_lbmolph": "",
            "global_mass_closure_error_abs_max_lbmolph": "",
            "exact_command_dup_group": "",
            "exact_command_dup_count": "",
            "suspected_dup_group": "",
            "suspected_dup_count": "",
            "suspected_duplicate": "0",
        }

        if status == "ok" and first is not None and last is not None:
            row["t_final_s"] = _safe_float_text(last.get("time_s"))
            row["P_top_pv_psia_final"] = _choose_p_top(last)
            row["P_top_sp_psia_final"] = _safe_float_text(last.get("P_top_psia_spec"))
            row["xD_pv_final"] = _safe_float_text(last.get("xD_comp_pv"))
            row["xD_sp_final"] = _safe_float_text(last.get("xD_comp_sp"))
            row["xB_pv_final"] = _safe_float_text(last.get("xB_comp_pv"))
            row["xB_sp_final"] = _safe_float_text(last.get("xB_comp_sp"))
            row["Reflux_cmd_lbmolph_final"] = _safe_float_text(last.get("Reflux_cmd_lbmolph"))
            row["Boilup_cmd_lbmolph_final"] = _safe_float_text(last.get("Boilup_cmd_lbmolph"))
            row["D_lbmolph_final"] = _safe_float_text(last.get("D_lbmolph"))
            row["B_lbmolph_final"] = _safe_float_text(last.get("B_lbmolph"))
            row["TopL_init_lbmol"] = _safe_float_text(first.get("Distillate_L_lbmol"))
            row["TopL_final_lbmol"] = _safe_float_text(last.get("Distillate_L_lbmol"))
            row["BotL_init_lbmol"] = _safe_float_text(first.get("Bottoms_L_lbmol"))
            row["BotL_final_lbmol"] = _safe_float_text(last.get("Bottoms_L_lbmol"))
            row["global_mass_closure_error_final_lbmolph"] = _safe_float_text(last.get("global_mass_closure_error_lbmolph"))
            row["global_mass_closure_error_abs_max_lbmolph"] = _mass_error_abs_max(summary_path)

        rows.append(_row_to_record(row))
        seen_run_ids.add(run_id)

    for run_id, feas_path in _iter_feasibility_files(logs):
        if run_id in seen_run_ids:
            continue
        run_dt = datetime.strptime(run_id, "%Y%m%d_%H%M%S")
        run_dt_txt = run_dt.strftime("%Y-%m-%d %H:%M:%S")
        best, status = _read_feasibility_best(feas_path)

        src = "unknown"
        cmd = ""
        if run_id in known_cmd_map:
            src, cmd = known_cmd_map[run_id]

        row = {
            "run_id": run_id,
            "run_datetime_local": run_dt_txt,
            "status": status,
            "command_source": src,
            "cli_command": cmd,
            "summary_csv": _relative_path(feas_path, root),
            "profile_csv": "",
            "t_final_s": "",
            "P_top_pv_psia_final": "",
            "P_top_sp_psia_final": "",
            "xD_pv_final": "",
            "xD_sp_final": "",
            "xB_pv_final": "",
            "xB_sp_final": "",
            "Reflux_cmd_lbmolph_final": "",
            "Boilup_cmd_lbmolph_final": "",
            "D_lbmolph_final": "",
            "B_lbmolph_final": "",
            "TopL_init_lbmol": "",
            "TopL_final_lbmol": "",
            "BotL_init_lbmol": "",
            "BotL_final_lbmol": "",
            "global_mass_closure_error_final_lbmolph": "",
            "global_mass_closure_error_abs_max_lbmolph": "",
            "exact_command_dup_group": "",
            "exact_command_dup_count": "",
            "suspected_dup_group": "",
            "suspected_dup_count": "",
            "suspected_duplicate": "0",
        }
        if status == "ok" and best is not None:
            row["P_top_pv_psia_final"] = _safe_float_text(best.get("P_top_psia"))
            row["P_top_sp_psia_final"] = _safe_float_text(best.get("P_top_sp_psia"))
            row["xD_pv_final"] = _safe_float_text(best.get("xD"))
            row["xD_sp_final"] = _safe_float_text(best.get("xD_sp"))
            row["xB_pv_final"] = _safe_float_text(best.get("xB"))
            row["xB_sp_final"] = _safe_float_text(best.get("xB_sp"))
            row["Reflux_cmd_lbmolph_final"] = _safe_float_text(best.get("reflux_lbmolph"))
            row["Boilup_cmd_lbmolph_final"] = _safe_float_text(best.get("boilup_lbmolph"))
            row["global_mass_closure_error_final_lbmolph"] = _safe_float_text(best.get("global_mass_closure_error_lbmolph"))

        rows.append(_row_to_record(row))
        seen_run_ids.add(run_id)

    rows.sort(key=lambda r: r.run_id, reverse=True)

    cmd_dup_group_by_run, cmd_dup_count_by_run, cmd_dup_summary = _compute_exact_command_duplicates(rows)
    sig_dup_group_by_run, sig_dup_count_by_run, sig_dup_summary = _compute_suspected_duplicates(rows)
    rows_enriched: List[RunRecord] = []
    for r in rows:
        row = dict(r.__dict__)

        cmd_count = cmd_dup_count_by_run.get(r.run_id)
        if cmd_count is not None:
            row["exact_command_dup_count"] = str(cmd_count)
        else:
            row["exact_command_dup_count"] = "1" if str(r.cli_command or "").strip() else ""
        row["exact_command_dup_group"] = cmd_dup_group_by_run.get(r.run_id, "")

        sig_count = sig_dup_count_by_run.get(r.run_id)
        row["suspected_dup_count"] = str(sig_count) if sig_count is not None else ""
        row["suspected_dup_group"] = sig_dup_group_by_run.get(r.run_id, "")
        row["suspected_duplicate"] = "1" if sig_count is not None else "0"

        rows_enriched.append(_row_to_record(row))
    rows = rows_enriched

    fields = [
        "run_id",
        "run_datetime_local",
        "status",
        "command_source",
        "cli_command",
        "summary_csv",
        "profile_csv",
        "t_final_s",
        "P_top_pv_psia_final",
        "P_top_sp_psia_final",
        "xD_pv_final",
        "xD_sp_final",
        "xB_pv_final",
        "xB_sp_final",
        "Reflux_cmd_lbmolph_final",
        "Boilup_cmd_lbmolph_final",
        "D_lbmolph_final",
        "B_lbmolph_final",
        "TopL_init_lbmol",
        "TopL_final_lbmol",
        "BotL_init_lbmol",
        "BotL_final_lbmol",
        "global_mass_closure_error_final_lbmolph",
        "global_mass_closure_error_abs_max_lbmolph",
        "exact_command_dup_group",
        "exact_command_dup_count",
        "suspected_dup_group",
        "suspected_dup_count",
        "suspected_duplicate",
    ]

    with ledger_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r.__dict__)

    known = [r for r in rows if r.command_source.lower() != "unknown"]
    unknown = [r for r in rows if r.command_source.lower() == "unknown"]
    cmd_dup_rows = sum(c for _gid, c, _runs in cmd_dup_summary)
    sig_dup_rows = sum(c for _gid, c, _runs in sig_dup_summary)

    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with ledger_md.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Experiment Ledger\n\n")
        f.write(f"Updated: {now_txt} (local)\n\n")
        f.write(
            "This file is auto-generated from `logs/column_summary_*.csv`, "
            "`logs/feasibility_trim_search_*.csv`, and `logs/run_registry.csv`.\n\n"
        )
        f.write(f"Total runs indexed: **{len(rows)}**  \n")
        f.write(f"Runs with known CLI command: **{len(known)}**  \n")
        f.write(f"Runs with unknown CLI command: **{len(unknown)}**\n\n")
        f.write("Primary searchable source: `docs/experiment_ledger.csv`.\n\n")
        f.write("Duplicate indicators in CSV: `exact_command_dup_group`, `exact_command_dup_count`, ")
        f.write("`suspected_dup_group`, `suspected_dup_count`, `suspected_duplicate`.\n\n")

        f.write("## Duplicate Signals\n\n")
        f.write(f"Exact-command duplicate groups: **{len(cmd_dup_summary)}** (rows in groups: **{cmd_dup_rows}**)  \n")
        f.write(f"Suspected-result duplicate groups: **{len(sig_dup_summary)}** (rows in groups: **{sig_dup_rows}**)\n\n")
        if cmd_dup_summary:
            f.write("### Exact Command Duplicates (Top 20)\n\n")
            f.write("| Group | Count | Run IDs |\n")
            f.write("|---|---:|---|\n")
            for gid, cnt, run_ids in cmd_dup_summary[:20]:
                f.write(f"| `{gid}` | {cnt} | {', '.join(f'`{x}`' for x in run_ids)} |\n")
            f.write("\n")
        if sig_dup_summary:
            f.write("### Suspected Result Duplicates (Top 30)\n\n")
            f.write("| Group | Count | Run IDs |\n")
            f.write("|---|---:|---|\n")
            for gid, cnt, run_ids in sig_dup_summary[:30]:
                f.write(f"| `{gid}` | {cnt} | {', '.join(f'`{x}`' for x in run_ids)} |\n")
            f.write("\n")

        f.write("## Known CLI Commands\n\n")
        f.write("| Run ID | Date/Time | Source | Command | Final (P, xD, xB, R, Vb) |\n")
        f.write("|---|---|---|---|---|\n")
        for r in sorted(known, key=lambda x: x.run_id, reverse=True):
            summary = (
                f"P={_fmt_float_text(r.P_top_pv_psia_final,3)}; "
                f"xD={_fmt_float_text(r.xD_pv_final,6)}; "
                f"xB={_fmt_float_text(r.xB_pv_final,6)}; "
                f"R={_fmt_float_text(r.Reflux_cmd_lbmolph_final,2)}; "
                f"Vb={_fmt_float_text(r.Boilup_cmd_lbmolph_final,2)}"
            )
            cmd = r.cli_command.replace("|", "\\|")
            f.write(
                f"| `{r.run_id}` | {r.run_datetime_local} | `{r.command_source}` | `{cmd}` | {summary} |\n"
            )

        f.write("\n## Recent Runs (Latest 60)\n\n")
        f.write("| Run ID | Status | CLI Known | t_final(s) | P_top | xD | xB | Reflux | Boilup | D | B | Summary CSV |\n")
        f.write("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for r in rows[:60]:
            f.write(
                f"| `{r.run_id}` | `{r.status}` | "
                f"{'Yes' if r.command_source.lower() != 'unknown' else 'No'} | "
                f"{_fmt_float_text(r.t_final_s,1)} | "
                f"{_fmt_float_text(r.P_top_pv_psia_final,3)} | "
                f"{_fmt_float_text(r.xD_pv_final,6)} | "
                f"{_fmt_float_text(r.xB_pv_final,6)} | "
                f"{_fmt_float_text(r.Reflux_cmd_lbmolph_final,2)} | "
                f"{_fmt_float_text(r.Boilup_cmd_lbmolph_final,2)} | "
                f"{_fmt_float_text(r.D_lbmolph_final,2)} | "
                f"{_fmt_float_text(r.B_lbmolph_final,2)} | "
                f"`{r.summary_csv}` |\n"
            )

    return ledger_csv, ledger_md, len(rows)
