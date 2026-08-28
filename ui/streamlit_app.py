from __future__ import annotations

import datetime as dt
import html
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for _path in (PROJECT_ROOT, SRC_ROOT):
    _txt = str(_path)
    if _txt not in sys.path:
        sys.path.insert(0, _txt)

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

from ui.data_access import (
    compact_stage_table,
    extract_warning_lines,
    latest_stage_snapshot,
    latest_summary_row,
    load_column_overview,
    read_runner_phase,
    read_profile_df,
    read_run_metadata,
    read_summary_df,
    validate_excel_input,
)
from ui.run_manager import (
    active_run_status,
    build_launch_spec,
    build_launch_spec_from_cli,
    clear_active_run,
    discover_excel_files,
    inspect_stored_state,
    launch_simulation,
    read_active_run,
    request_runtime_extension,
    resume_pid,
    save_uploaded_excel_bytes,
    save_uploaded_state_bytes,
    suspend_pid,
    terminate_pid,
    update_active_run,
)
from ui.schematic import build_column_schematic_html


def _fmt_metric(value: Any, *, nd: int = 2) -> str:
    try:
        v = float(value)
    except Exception:
        return "n/a"
    if v != v:
        return "n/a"
    return f"{v:.{nd}f}"


def _fmt_hms(value: Any) -> str:
    try:
        total_seconds = float(value)
    except Exception:
        return "n/a"
    if total_seconds != total_seconds or total_seconds < 0.0:
        return "n/a"
    total_seconds_i = int(round(total_seconds))
    hours = total_seconds_i // 3600
    minutes = (total_seconds_i % 3600) // 60
    seconds = total_seconds_i % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _open_local_path(path: Any) -> None:
    target = Path(str(path or "")).expanduser()
    if not target.exists():
        raise FileNotFoundError(str(target))
    os.startfile(str(target))  # type: ignore[attr-defined]


def _remaining_sim_time_seconds(active: Dict[str, Any], summary_row: Dict[str, Any]) -> Optional[float]:
    try:
        n_steps = float(active.get("n_steps"))
        dt_sec = float(active.get("dt_sec"))
        sim_time = float(summary_row.get("time_s"))
    except Exception:
        return None
    if not (n_steps == n_steps and dt_sec == dt_sec and sim_time == sim_time):
        return None
    total_sim = max(n_steps * dt_sec, 0.0)
    remaining = max(total_sim - sim_time, 0.0)
    return float(remaining)


def _remaining_wall_time_seconds(active: Dict[str, Any], summary_row: Dict[str, Any]) -> Optional[float]:
    try:
        sim_time = float(summary_row.get("time_s"))
        wall_elapsed = float(summary_row.get("wall_elapsed_s"))
    except Exception:
        return None
    if not (sim_time == sim_time and wall_elapsed == wall_elapsed):
        return None
    if sim_time <= 0.0 or wall_elapsed < 0.0:
        return None
    remaining_sim = _remaining_sim_time_seconds(active, summary_row)
    if remaining_sim is None:
        return None
    return float((wall_elapsed / sim_time) * remaining_sim)


def _render_summary_metrics(summary_row: Dict[str, Any]) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    sim_time = summary_row.get("time_s")
    elapsed = summary_row.get("wall_elapsed_s")
    ratio = None
    try:
        sim = float(sim_time)
        wall = float(elapsed)
        if sim > 0.0:
            ratio = wall / sim
    except Exception:
        ratio = None
    c1.metric("Sim Time", _fmt_hms(sim_time))
    c2.metric("Elapsed", _fmt_hms(elapsed))
    c3.metric("Elapsed/Sim", _fmt_metric(ratio))
    c4.metric("SS Score", _fmt_metric(summary_row.get("steady_state_score"), nd=3))
    c5.metric("Remaining Simulation Time", _fmt_hms(None))
    c6.metric("Remaining Wall Time", _fmt_hms(None))


def _wall_elapsed_from_active(active: Dict[str, Any]) -> Optional[float]:
    started = str(active.get("started_at_local", "") or "").strip()
    if not started:
        return None
    try:
        started_dt = dt.datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    now = dt.datetime.now()
    elapsed = (now - started_dt).total_seconds()
    if elapsed < 0.0:
        return None
    return float(elapsed)


def _render_progress_metrics(active: Dict[str, Any], summary_row: Dict[str, Any]) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    sim_time = summary_row.get("time_s")
    elapsed_logged = summary_row.get("wall_elapsed_s")
    has_logged_summary = bool(summary_row) and sim_time not in (None, "")
    elapsed_total = _wall_elapsed_from_active(active)
    elapsed = elapsed_logged
    try:
        logged_val = float(elapsed_logged)
    except Exception:
        logged_val = None
    try:
        total_val = float(elapsed_total)
    except Exception:
        total_val = None
    is_live = str(active.get("status", "")).strip().lower() == "running"
    if has_logged_summary and is_live and total_val is not None and total_val == total_val:
        if logged_val is None or logged_val != logged_val or total_val > logged_val:
            elapsed = total_val
    elif not has_logged_summary:
        elapsed = total_val if (total_val is not None and total_val == total_val and total_val >= 0.0) else 0.0
    ratio = None
    try:
        sim = float(sim_time)
        wall = float(elapsed)
        if sim > 0.0:
            ratio = wall / sim
    except Exception:
        ratio = None
    remaining_sim = _remaining_sim_time_seconds(active, summary_row)
    remaining_wall = _remaining_wall_time_seconds(active, summary_row)
    c1.metric("Sim Time", _fmt_hms(sim_time))
    c2.metric("Elapsed", _fmt_hms(elapsed))
    c3.metric("Elapsed/Sim", _fmt_metric(ratio))
    c4.metric("SS Score", _fmt_metric(summary_row.get("steady_state_score"), nd=3))
    c5.metric("Remaining Simulation Time", _fmt_hms(remaining_sim))
    c6.metric("Remaining Wall Time", _fmt_hms(remaining_wall))
    if has_logged_summary and is_live and total_val is not None and logged_val is not None and total_val > logged_val + 5.0:
        st.caption(
            "Elapsed includes startup and conditioning time before summary rows begin logging."
        )


def _trend_chart(summary_df: pd.DataFrame, column: str, label: str) -> None:
    raise NotImplementedError


def _level_axis_unit(specs_raw: Dict[str, Any], which: str) -> str:
    key = "Top Level PV Mode" if which == "top" else "Bottom Level PV Mode"
    mode = str(specs_raw.get(key, "") or "").strip().lower()
    if mode == "true-level":
        return "fraction (-)"
    return "lbmol"


def _spec_first(specs_raw: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in specs_raw and specs_raw.get(key) not in ("", None):
            return specs_raw.get(key)
    return None


def _with_bottom_level_fraction(summary_df: pd.DataFrame, overview: Dict[str, Any]) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df
    out = summary_df.copy()
    if "Bottom_level_fraction" in out.columns:
        return out
    frac = pd.to_numeric(out.get("Bottom_level_ctrl_pv"), errors="coerce")
    mode = str(overview.get("bottom_level_pv_mode") or "").strip().lower()
    if mode == "true-level":
        out["Bottom_level_fraction"] = frac
        return out

    specs_raw = dict(overview.get("specs_raw", {}) or {})
    live_holdup = pd.to_numeric(out.get("Bottoms_L_lbmol"), errors="coerce")
    if live_holdup.notna().any():
        frac = live_holdup

    nominal_frac = pd.to_numeric(
        pd.Series(
            [
                _spec_first(
                    specs_raw,
                    "Bottom Sump Liquid Fraction (-)",
                    "Bottom Sump Liquid Fraction",
                    "Bottom Level SP Frac",
                )
            ]
            * len(out),
            index=out.index,
        ),
        errors="coerce",
    )
    nominal_holdup = pd.to_numeric(
        pd.Series(
            [
                _spec_first(
                    specs_raw,
                    "Bottom Holdup (lbmol)",
                    "Bottom  Holdup (lbmol)",
                    "Bottom Level Holdup (lbmol)",
                )
            ]
            * len(out),
            index=out.index,
        ),
        errors="coerce",
    )
    converted = frac * nominal_frac / nominal_holdup
    out["Bottom_level_fraction"] = converted.clip(lower=0.0, upper=1.0)
    return out


def _series_label_from_column(column: str) -> str:
    txt = str(column)
    for prefix in ("Distillate_x_", "Bottoms_x_"):
        if txt.startswith(prefix):
            return txt[len(prefix):].replace("_", " ")
    return txt


def _composition_change_table(summary_df: pd.DataFrame, columns: Any) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for column in [str(item) for item in list(columns)]:
        if column not in summary_df.columns:
            continue
        values = pd.to_numeric(summary_df[column], errors="coerce").dropna()
        if values.empty:
            continue
        initial = float(values.iloc[0])
        current = float(values.iloc[-1])
        rows.append(
            {
                "Component": _series_label_from_column(column),
                "Initial": initial,
                "Current": current,
                "Change": current - initial,
            }
        )
    return pd.DataFrame(rows, columns=["Component", "Initial", "Current", "Change"])


def _composition_column_config(columns: Any) -> Dict[str, Any]:
    return {
        str(column): st.column_config.NumberColumn(format="%.7f")
        for column in columns
    }


def _render_composition_change_table(summary_df: pd.DataFrame, columns: Any) -> None:
    table = _composition_change_table(summary_df, columns)
    if table.empty:
        return
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=142,
        column_config={
            "Initial": st.column_config.NumberColumn(format="%.7f"),
            "Current": st.column_config.NumberColumn(format="%.7f"),
            "Change": st.column_config.NumberColumn(format="%+.7f"),
        },
    )


def _trend_chart(
    summary_df: pd.DataFrame,
    columns: Any,
    label: str,
    *,
    y_unit: str = "",
    x_unit: str = "s",
    height: int = 220,
    exclude_time_zero: bool = False,
) -> None:
    if summary_df.empty or "time_s" not in summary_df.columns:
        st.info(f"{label}: no data yet")
        return
    if isinstance(columns, str):
        cols = [columns]
    else:
        cols = [str(c) for c in list(columns)]
    cols = [c for c in cols if c in summary_df.columns]
    if not cols:
        st.info(f"{label}: no data yet")
        return

    chart_df = summary_df[["time_s", *cols]].copy()
    if exclude_time_zero:
        chart_df = chart_df.loc[pd.to_numeric(chart_df["time_s"], errors="coerce") > 0.0].copy()
    chart_df = chart_df.melt(id_vars=["time_s"], value_vars=cols, var_name="series", value_name="value")
    chart_df = chart_df.dropna(subset=["value"])
    if chart_df.empty:
        st.info(f"{label}: no data yet")
        return
    chart_df["series_label"] = chart_df["series"].map(_series_label_from_column)

    y_domain = None
    try:
        y_min = float(chart_df["value"].min())
        y_max = float(chart_df["value"].max())
        if y_min == y_min and y_max == y_max:
            if abs(y_max - y_min) < 1e-12:
                pad = max(abs(y_max) * 0.05, 1e-6)
            else:
                pad = max((y_max - y_min) * 0.08, 1e-6)
            y_domain = [y_min - pad, y_max + pad]
    except Exception:
        y_domain = None

    y_title = f"{label} ({y_unit})" if str(y_unit).strip() else label
    x_title = f"Time ({x_unit})" if str(x_unit).strip() else "Time"
    scale_kwargs: Dict[str, Any] = {
        "zero": False,
        "nice": False if y_domain is not None else True,
    }
    if y_domain is not None:
        scale_kwargs["domain"] = y_domain
    base = alt.Chart(chart_df).encode(
        x=alt.X("time_s:Q", title=x_title),
        y=alt.Y(
            "value:Q",
            title=y_title,
            scale=alt.Scale(**scale_kwargs),
        ),
        tooltip=[
            alt.Tooltip("time_s:Q", title="Time (s)", format=".3f"),
            alt.Tooltip("series_label:N", title="Series"),
            alt.Tooltip("value:Q", title=label, format=".6g"),
        ],
    )
    if len(cols) == 1:
        chart = base.mark_line(point=False).properties(height=height)
    else:
        chart = base.mark_line(point=False).encode(
            color=alt.Color("series_label:N", title="Series")
        ).properties(height=height)
    st.altair_chart(chart, use_container_width=True)


def _command_option_value(command: List[Any], flag: str) -> str:
    try:
        idx = list(command).index(flag)
    except Exception:
        return ""
    if idx + 1 >= len(command):
        return ""
    return str(command[idx + 1])


def _stringify_config_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        try:
            fval = float(value)
        except Exception:
            return str(value)
        if fval != fval:
            return ""
        if abs(fval - round(fval)) < 1e-12:
            return str(int(round(fval)))
        return f"{fval:.6g}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if isinstance(value, (list, tuple)):
        return ", ".join(_stringify_config_value(v) for v in value)
    return str(value)


def _config_table_from_mapping(mapping: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for key in sorted(mapping.keys(), key=lambda x: str(x).lower()):
        rows.append({"Parameter": str(key), "Value": _stringify_config_value(mapping.get(key))})
    return pd.DataFrame(rows)


def _discover_thermo_tables() -> List[Path]:
    cache_dir = PROJECT_ROOT / "cache"
    if not cache_dir.exists():
        return []
    return sorted(p.resolve() for p in cache_dir.glob("*.json"))


def _thermo_table_option_label(value: str) -> str:
    if value == "":
        return "Default (cache/thermo_table.json)"
    if value == "__custom__":
        return "Custom path..."
    path = Path(value)
    try:
        rel = path.relative_to(PROJECT_ROOT)
        return str(rel)
    except Exception:
        return str(path)


def _selected_thermo_table_path() -> str:
    selected = str(st.session_state.get("thermo_table_choice_override", "") or "")
    if selected == "__custom__":
        return str(st.session_state.get("thermo_table_path_override", "") or "").strip()
    return selected.strip()


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        v = float(value)
        return v == v
    except Exception:
        return True


def _resolved_row(
    parameter: str,
    *,
    workbook_value: Any = None,
    ui_value: Any = None,
    default_value: Any = None,
) -> Dict[str, Any]:
    if _has_value(ui_value):
        effective = ui_value
        source = "UI override"
    elif _has_value(workbook_value):
        effective = workbook_value
        source = "Workbook"
    else:
        effective = default_value
        source = "Runner default"
    return {
        "Parameter": parameter,
        "Effective Value": _stringify_config_value(effective),
        "Source": source,
        "Workbook Value": _stringify_config_value(workbook_value),
        "UI Value": _stringify_config_value(ui_value),
        "Runner Default": _stringify_config_value(default_value),
    }


def _effective_config_rows(preview_spec: Optional[Any], specs_raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    ui_runtime_mode = getattr(preview_spec, "runtime_mode", None) or st.session_state.get("runtime_mode_override", "hydraulic")
    ui_thermo_mode = getattr(preview_spec, "thermo_mode", None) or st.session_state.get("thermo_mode_override", "table-pool")
    ui_dwsim_property_package = getattr(preview_spec, "dwsim_property_package", None) or st.session_state.get(
        "dwsim_property_package_override", "pr"
    )
    ui_thermo_table = (
        str(getattr(preview_spec, "thermo_table_path", "") or _selected_thermo_table_path())
        if str(ui_thermo_mode) in {"table", "table-pool"}
        else None
    )
    ui_pool_workers = getattr(preview_spec, "thermo_pool_workers", None)
    if ui_pool_workers is None:
        ui_pool_workers = st.session_state.get("thermo_pool_workers_override", 2)
    ui_pool_chunk = getattr(preview_spec, "thermo_pool_chunk_size", None)
    if ui_pool_chunk is None:
        ui_pool_chunk = st.session_state.get("thermo_pool_chunk_size_override", 4)
    ui_thermo_every = getattr(preview_spec, "thermo_every_n_steps", None)
    if ui_thermo_every is None:
        ui_thermo_every = st.session_state.get("thermo_every_override", 1)
    ui_fast_startup = getattr(preview_spec, "fast_startup_override", None)
    if ui_fast_startup is None:
        ui_fast_startup = st.session_state.get("fast_startup_override", "Off")
    ui_anchor_blend = getattr(preview_spec, "thermo_table_anchor_blend_count", None)
    if ui_anchor_blend is None:
        ui_anchor_blend = st.session_state.get("thermo_anchor_blend_count_override", 3)
    ui_eqpr = getattr(preview_spec, "equilibrium_relaxation_live_pr_override", None)
    if ui_eqpr is None:
        ui_eqpr = st.session_state.get("equilibrium_relaxation_live_pr_override", "Off")
    ui_integrator = getattr(preview_spec, "integrator", None) or st.session_state.get("integrator_override", "explicit-euler")
    ui_energy = getattr(preview_spec, "include_energy_override", None)
    if ui_energy is None:
        ui_energy = st.session_state.get("include_energy_override", "Off")

    rows = [
        _resolved_row("Excel Path", workbook_value=specs_raw.get("Excel Path"), ui_value=str(getattr(preview_spec, "excel_path", "") or "")),
        _resolved_row(
            "Simulation Length (min)",
            workbook_value=specs_raw.get("Simulation Length (min)"),
            ui_value=(float(getattr(preview_spec, "n_steps", 0)) * float(getattr(preview_spec, "dt_sec", 0.0)) / 60.0) if preview_spec else None,
        ),
        _resolved_row("n_steps", ui_value=getattr(preview_spec, "n_steps", None)),
        _resolved_row("dt_sec", workbook_value=specs_raw.get("Timestep (sec)"), ui_value=getattr(preview_spec, "dt_sec", None)),
        _resolved_row(
            "log_every_n_steps",
            workbook_value=specs_raw.get("Log Frequency (timesteps)"),
            ui_value=getattr(preview_spec, "log_every_n_steps", None),
        ),
        _resolved_row(
            "Runtime Mode",
            ui_value=ui_runtime_mode,
            default_value="parity",
        ),
        _resolved_row(
            "Thermo Mode",
            ui_value=ui_thermo_mode,
            default_value="table-pool",
        ),
        _resolved_row(
            "DWSIM Property Package",
            ui_value=(ui_dwsim_property_package if str(ui_thermo_mode) == "dwsim" else None),
            default_value="pr",
        ),
        _resolved_row(
            "Thermo Table",
            ui_value=ui_thermo_table,
            default_value=r"cache/thermo_table.json",
        ),
        _resolved_row(
            "Table Anchor Blend Count",
            ui_value=int(ui_anchor_blend),
            default_value=3,
        ),
        _resolved_row(
            "Pool Workers",
            ui_value=int(ui_pool_workers),
            default_value=2,
        ),
        _resolved_row(
            "Pool Chunk Size",
            ui_value=int(ui_pool_chunk),
            default_value=4,
        ),
        _resolved_row(
            "Thermo Every N Steps",
            workbook_value=specs_raw.get("Thermo Every N Steps"),
            ui_value=int(ui_thermo_every),
            default_value=1,
        ),
        _resolved_row(
            "Fast Startup",
            ui_value=(True if ui_fast_startup is True or ui_fast_startup == "On" else None),
            default_value=False,
        ),
        _resolved_row(
            "Eq-Relax Live PR",
            workbook_value=specs_raw.get("Equilibrium Relaxation Live PR"),
            ui_value=(True if ui_eqpr is True or ui_eqpr == "On" else None),
            default_value=False,
        ),
        _resolved_row(
            "Include Energy",
            ui_value=(True if ui_energy is True or ui_energy == "On" else None),
            default_value=False,
        ),
        _resolved_row(
            "Integrator",
            ui_value=ui_integrator,
            default_value="explicit-euler",
        ),
    ]

    workbook_labels = [
        "Condenser Duty (Btu/h)",
        "Reboiler Duty (Btu/h)",
        "Pressure Model",
        "Vapor Flow Model",
        "Stage time constant [tau] (sec)",
        "Equilibrium Relaxation Mode",
        "Equilibrium Tau (sec)",
        "Equilibrium Energy Damping Gain",
        "Hydraulic Energy Temperature Follow Tau (sec)",
        "Enable Level Control",
        "Top Level PV Mode",
        "Top Level SP Frac",
        "Top Level Kc",
        "Top Level Ti (sec)",
        "Bottom Level PV Mode",
        "Bottom Level SP Frac",
        "Bottom Level Kc",
        "Bottom Level Ti (sec)",
        "Enable Pressure Control",
        "Pressure Control MV",
        "Top Pressure SP (psia)",
        "Top Pressure Kc",
        "Top Pressure Ti (sec)",
        "Enable Distillate Composition Control",
        "Distillate Composition Component",
        "Distillate Composition SP",
        "Distillate Composition Kc",
        "Distillate Composition Ti (sec)",
        "Distillate Composition Reflux Min (lbmol/h)",
        "Distillate Composition Reflux Max (lbmol/h)",
        "Vapor Holdup Relaxation (sec)",
        "Vapor Flow Relaxation (sec)",
        "Dry Tray K",
        "Top Drum Diameter (ft)",
        "Top Drum Length (ft)",
        "Top Drum Liquid Fraction (-)",
        "Bottom Sump Diameter (ft)",
        "Bottom Sump Height (ft)",
        "Bottom Sump Liquid Fraction (-)",
    ]
    for label in workbook_labels:
        rows.append(_resolved_row(label, workbook_value=specs_raw.get(label)))
    return rows


def _stage_profile_panel(
    snapshot: pd.DataFrame,
    component_names: List[str],
    *,
    pressure_profile_psia: Optional[List[Any]] = None,
) -> None:
    if snapshot.empty:
        st.info("No stage profile rows yet.")
        return
    if "node_type" in snapshot.columns:
        tray_snapshot = snapshot.loc[snapshot["node_type"].astype(str).str.lower() == "tray"].copy()
        if not tray_snapshot.empty:
            snapshot = tray_snapshot
    table = compact_stage_table(
        snapshot,
        component_names=component_names,
        pressure_profile_psia=pressure_profile_psia,
    )
    st.dataframe(table, use_container_width=True, height=520)


def _safe_load_column_overview(excel_path: Optional[Path]) -> Dict[str, Any]:
    if excel_path is None or not excel_path.exists():
        return {}
    try:
        return load_column_overview(excel_path)
    except Exception:
        return {}


def _render_browser_autorefresh(interval_sec: int) -> None:
    interval_ms = max(int(interval_sec), 1) * 1000
    components.html(
        f"""
        <script>
        const intervalMs = {interval_ms};
        const key = "dynamic-distillation-autorefresh";
        const current = window.sessionStorage.getItem(key);
        if (current !== String(intervalMs)) {{
            window.sessionStorage.setItem(key, String(intervalMs));
        }}
        window.clearTimeout(window.__dynamicDistillationAutoRefreshTimer);
        window.__dynamicDistillationAutoRefreshTimer = window.setTimeout(() => {{
            window.parent.location.reload();
        }}, intervalMs);
        </script>
        """,
        height=0,
    )


def _render_startup_scroll_frame(
    *,
    completed_steps: List[str],
    recent_lines: List[str],
    height_px: int,
) -> None:
    safe_steps = "".join(
        f"<li>{html.escape(str(step))}</li>"
        for step in completed_steps
    )
    safe_recent = "\n".join(html.escape(str(line)) for line in recent_lines)
    components.html(
        f"""
        <div style="
            height:{int(max(height_px, 180))}px;
            overflow-y:auto;
            border:1px solid rgba(250,250,250,0.10);
            border-radius:12px;
            padding:16px 18px;
            background:rgba(255,255,255,0.02);
            box-sizing:border-box;
        ">
          <div style="font-size:1.1rem;font-weight:700;margin-bottom:10px;color:#fafafa;">Startup Steps</div>
          <ul style="margin:0 0 20px 18px;padding:0;color:#fafafa;line-height:1.7;">
            {safe_steps or "<li>No startup steps recorded yet.</li>"}
          </ul>
          <div style="font-size:1.1rem;font-weight:700;margin-bottom:10px;color:#fafafa;">Recent Startup Detail</div>
          <pre style="
            margin:0;
            white-space:pre-wrap;
            word-break:break-word;
            color:#fafafa;
            background:rgba(255,255,255,0.04);
            border-radius:10px;
            padding:14px;
            font-size:0.95rem;
            line-height:1.45;
            font-family:Consolas, 'Courier New', monospace;
          ">{safe_recent or "No startup detail yet."}</pre>
        </div>
        """,
        height=int(max(height_px, 180) + 12),
        scrolling=False,
    )


def _reset_form_state(*, include_launch_mode: bool = True) -> None:
    widget_keys = [
        "launch_mode",
        "initialization_mode",
        "cli_command_text",
        "run_name",
        "run_description",
        "runtime_mode_override",
        "thermo_mode_override",
        "dwsim_property_package_override",
        "thermo_table_choice_override",
        "thermo_table_path_override",
        "thermo_pool_workers_override",
        "thermo_pool_chunk_size_override",
        "thermo_every_override",
        "fast_startup_override",
        "thermo_anchor_blend_count_override",
        "equilibrium_relaxation_live_pr_override",
        "integrator_override",
        "include_energy_override",
        "add_time_seconds",
        "stored_state_path_input",
        "core_v3_duration_sec",
        "core_v3_log_every_n_steps",
    ]
    if not include_launch_mode:
        widget_keys = [key for key in widget_keys if key != "launch_mode"]
    for key in widget_keys:
        st.session_state.pop(key, None)
    st.session_state["uploaded_excel_path"] = ""
    st.session_state["uploaded_excel_sig"] = None
    st.session_state["uploaded_state_path"] = ""
    st.session_state["uploaded_state_sig"] = None
    st.session_state["input_validation_report"] = {}
    st.session_state["input_validation_excel_path"] = ""
    st.session_state["excel_upload_nonce"] = int(st.session_state.get("excel_upload_nonce", 0)) + 1
    st.session_state["state_upload_nonce"] = int(st.session_state.get("state_upload_nonce", 0)) + 1


def _request_clear_ui() -> None:
    st.session_state["_request_clear_ui"] = True


def _request_reset_ui() -> None:
    st.session_state["_request_reset_ui"] = True


def _clear_validation_state() -> None:
    st.session_state["input_validation_report"] = {}
    st.session_state["input_validation_excel_path"] = ""


def _current_excel_selection() -> Optional[Path]:
    excel_candidates = discover_excel_files()
    default_path = None
    for candidate in excel_candidates:
        if candidate.name == "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx" and candidate.parent == PROJECT_ROOT:
            default_path = candidate
            break
    if default_path is None and excel_candidates:
        default_path = excel_candidates[0]
    if "uploaded_excel_path" not in st.session_state:
        st.session_state["uploaded_excel_path"] = ""
    if "uploaded_excel_sig" not in st.session_state:
        st.session_state["uploaded_excel_sig"] = None
    if "excel_upload_nonce" not in st.session_state:
        st.session_state["excel_upload_nonce"] = 0

    uploaded = st.sidebar.file_uploader(
        "Upload Excel file",
        type=["xlsx"],
        key=f"excel_upload_{int(st.session_state.get('excel_upload_nonce', 0))}",
    )
    if uploaded is not None:
        payload = uploaded.getvalue()
        sig = (uploaded.name, len(payload))
        if st.session_state.get("uploaded_excel_sig") != sig:
            saved = save_uploaded_excel_bytes(uploaded.name, payload)
            st.session_state["uploaded_excel_sig"] = sig
            st.session_state["uploaded_excel_path"] = str(saved)
        uploaded_path = Path(str(st.session_state.get("uploaded_excel_path", "")))
        if uploaded_path.exists():
            st.sidebar.success(f"Uploaded: {uploaded_path.name}")
            return uploaded_path
    saved_path = Path(str(st.session_state.get("uploaded_excel_path", ""))) if st.session_state.get("uploaded_excel_path") else None
    if saved_path and saved_path.exists():
        st.sidebar.caption(f"Using uploaded file: `{saved_path.name}`")
        return saved_path
    if default_path is not None:
        st.sidebar.caption(f"Using standard workbook: `{default_path.name}`")
        return Path(default_path)
    return None


def _current_stored_state_selection() -> Optional[Path]:
    if "uploaded_state_path" not in st.session_state:
        st.session_state["uploaded_state_path"] = ""
    if "uploaded_state_sig" not in st.session_state:
        st.session_state["uploaded_state_sig"] = None
    if "state_upload_nonce" not in st.session_state:
        st.session_state["state_upload_nonce"] = 0

    path_text = st.sidebar.text_input(
        "Stored State Path",
        key="stored_state_path_input",
        placeholder=r"C:\path\to\checkpoint.npz",
        help="Use a reusable Core V3 or legacy checkpoint produced by its dynamic runner.",
    )
    uploaded = st.sidebar.file_uploader(
        "Upload Stored State",
        type=["npz"],
        key=f"state_upload_{int(st.session_state.get('state_upload_nonce', 0))}",
        help="The uploaded file is copied into `.ui_state/uploads/` before launch.",
    )
    if uploaded is not None:
        payload = uploaded.getvalue()
        sig = (uploaded.name, len(payload))
        if st.session_state.get("uploaded_state_sig") != sig:
            saved = save_uploaded_state_bytes(uploaded.name, payload)
            st.session_state["uploaded_state_sig"] = sig
            st.session_state["uploaded_state_path"] = str(saved)
        uploaded_path = Path(str(st.session_state.get("uploaded_state_path", "")))
        if uploaded_path.exists():
            st.sidebar.success(f"Uploaded state: {uploaded_path.name}")
            return uploaded_path

    if str(path_text or "").strip():
        candidate = Path(str(path_text).strip()).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return candidate.resolve()

    saved_path = (
        Path(str(st.session_state.get("uploaded_state_path", "")))
        if st.session_state.get("uploaded_state_path")
        else None
    )
    if saved_path and saved_path.exists():
        st.sidebar.caption(f"Using uploaded state: `{saved_path.name}`")
        return saved_path
    accepted_core_v3 = PROJECT_ROOT / "logs" / "core_v3_checkpoints" / "dd274_endpoint_core_v3_checkpoint.npz"
    if accepted_core_v3.exists():
        st.sidebar.caption(f"Using accepted Core V3 state: `{accepted_core_v3.name}`")
        return accepted_core_v3.resolve()
    return None


def _render_live_dashboard(
    *,
    selected_excel_path: Optional[Path],
    preview_spec: Optional[Any],
) -> None:
    active = active_run_status(read_active_run())
    stdout_log = Path(str(active.get("stdout_log", ""))) if active.get("stdout_log") else None
    phase_info = read_runner_phase(stdout_log) if stdout_log is not None else {
        "phase": "idle",
        "message": "No active runner output.",
        "integration_started": False,
        "startup_in_progress": False,
        "latest_milestone": "",
        "latest_progress": "",
    }

    status_cols = st.columns([1, 1, 2, 2])
    status_cols[0].metric("Status", str(active.get("status", "idle")).upper())
    status_cols[1].metric("PID", str(active.get("pid", "n/a")))
    logs_dir_text = str(active.get("logs_dir", "") or "")
    excel_path_text = str(active.get("excel_path", "") or "")
    status_cols[2].write(f"Logs Dir: `{logs_dir_text}`")
    status_cols[3].write(f"Excel: `{excel_path_text}`")
    if active.get("excel_path"):
        initialization_mode = str(active.get("initialization_mode", "fresh") or "fresh")
        checkpoint_text = str(active.get("checkpoint_path", "") or "")
        if initialization_mode == "restart":
            st.caption(f"Initial state: restart from `{checkpoint_text}`")
        else:
            st.caption("Initial state: fresh start from Excel")
    open_cols = st.columns([1, 1, 2, 2])
    with open_cols[2]:
        if logs_dir_text:
            if st.button("Open Logs Folder", key="open_logs_folder_btn", use_container_width=True):
                try:
                    _open_local_path(logs_dir_text)
                except Exception as exc:
                    st.error(f"Could not open logs folder: {exc}")
    with open_cols[3]:
        if excel_path_text:
            if st.button("Open Excel Workbook", key="open_excel_workbook_btn", use_container_width=True):
                try:
                    _open_local_path(excel_path_text)
                except Exception as exc:
                    st.error(f"Could not open workbook: {exc}")
    if active.get("command"):
        with st.expander("Effective Launch Command", expanded=False):
            st.code(" ".join(str(x) for x in active["command"]), language="powershell")

    logs_dir = Path(str(active.get("logs_dir"))) if active.get("logs_dir") else None
    active_started_at_local = active.get("started_at_local", "")
    run_metadata = read_run_metadata(logs_dir, started_after_local=active_started_at_local) if logs_dir else {}
    summary_df = read_summary_df(logs_dir, started_after_local=active_started_at_local) if logs_dir else pd.DataFrame()
    profile_df = read_profile_df(logs_dir, started_after_local=active_started_at_local) if logs_dir else pd.DataFrame()
    stderr_log = Path(str(active.get("stderr_log", ""))) if active.get("stderr_log") else None
    startup_errors = extract_warning_lines(stderr_log, limit=10) if stderr_log is not None else []
    summary_row = latest_summary_row(summary_df)
    snapshot = latest_stage_snapshot(profile_df)
    active_excel_path = Path(str(active["excel_path"])) if active.get("excel_path") and Path(str(active["excel_path"])).exists() else None
    active_overview = _safe_load_column_overview(active_excel_path)
    preview_overview = _safe_load_column_overview(selected_excel_path)
    preview_validation = dict(st.session_state.get("input_validation_report", {}) or {})
    overview = active_overview
    component_names = list(overview.get("component_names", []) or [])

    if run_metadata:
        st.caption(
            f"Run ID `{run_metadata.get('run_id', '')}`  "
            f"Started {run_metadata.get('started_at_local', '')}  "
            f"Last status `{run_metadata.get('status', '')}`"
        )
    elif logs_dir and active.get("status") == "running":
        st.caption(
            f"Started {active_started_at_local}  "
            "Waiting for fresh run artifacts in the selected logs directory..."
        )
    _render_progress_metrics(active, summary_row)

    tabs = st.tabs(["Progress", "Trends", "Stage Profiles", "Column Schematic", "Run Configuration", "Warnings"])

    with tabs[0]:
        restart_workbook = str(run_metadata.get("restart_workbook", "") or "").strip()
        if restart_workbook:
            st.success(f"Restart workbook available: `{restart_workbook}`")
        if active.get("status") == "running":
            if phase_info.get("phase") == "startup":
                startup_frac = float(phase_info.get("startup_progress_fraction", 0.0) or 0.0)
                if startup_frac > 0.0:
                    st.progress(max(0.0, min(startup_frac, 1.0)), text=f"Startup progress: {int(round(startup_frac * 100.0))}%")
                if phase_info.get("latest_milestone"):
                    st.caption(f"Latest startup milestone: `{phase_info.get('latest_milestone')}`")
                completed = list(phase_info.get("startup_milestones_completed", []) or [])
                recent_lines = list(phase_info.get("startup_recent_lines", []) or [])
                startup_panel_height = int(st.session_state.get("startup_panel_height_px", 320) or 320)
                _render_startup_scroll_frame(
                    completed_steps=completed[-12:],
                    recent_lines=recent_lines[-12:],
                    height_px=startup_panel_height,
                )
            elif phase_info.get("phase") == "integration":
                if phase_info.get("latest_progress"):
                    st.caption(f"Latest progress line: `{phase_info.get('latest_progress')}`")
        if summary_df.empty:
            if active.get("status") == "stopped" and startup_errors:
                st.error("Run stopped during startup. See Warnings for the underlying error.")
            elif active.get("status") == "stopped":
                st.warning("Run is stopped and no summary data was written.")
            elif phase_info.get("phase") == "integration":
                st.info("Integration has started; waiting for the first logged summary row.")
            else:
                st.info("No summary data yet.")
        else:
            composition_columns = [
                column
                for column in summary_df.columns
                if str(column).startswith(("Distillate_x_", "Bottoms_x_"))
            ]
            st.dataframe(
                summary_df.tail(10),
                use_container_width=True,
                height=320,
                column_config=_composition_column_config(composition_columns),
            )

    with tabs[1]:
        specs_raw = dict(overview.get("specs_raw", {}) or {})
        trends_df = _with_bottom_level_fraction(summary_df, overview)
        distillate_comp_cols = [c for c in trends_df.columns if str(c).startswith("Distillate_x_")]
        bottoms_comp_cols = [c for c in trends_df.columns if str(c).startswith("Bottoms_x_")]

        row1 = st.columns(3)
        with row1[0]:
            st.subheader("Condenser Duty")
            _trend_chart(trends_df, "Q_cond_used_BTUph", "Condenser Duty", y_unit="Btu/h")
        with row1[1]:
            st.subheader("Reflux Rate")
            _trend_chart(trends_df, "Reflux_cmd_lbmolph", "Reflux Rate", y_unit="lbmol/h")
        with row1[2]:
            st.subheader("Distillate Flow")
            _trend_chart(trends_df, "D_lbmolph", "Distillate Flow", y_unit="lbmol/h")

        row2 = st.columns(3)
        with row2[0]:
            st.subheader("Distillate Drum Level")
            _trend_chart(trends_df, "Top_level_ctrl_pv", "Distillate Drum Level", y_unit=_level_axis_unit(specs_raw, "top"))
        with row2[1]:
            st.subheader("Distillate Drum Controller Output")
            _trend_chart(trends_df, "D_lbmolph", "Distillate Drum Controller Output", y_unit="lbmol/h")
        with row2[2]:
            st.subheader("Distillate Composition")
            _trend_chart(trends_df, distillate_comp_cols, "Distillate Composition", y_unit="mole fraction (-)")
            _render_composition_change_table(trends_df, distillate_comp_cols)

        row3 = st.columns(2)
        with row3[0]:
            st.subheader("Distillate Temperature")
            _trend_chart(trends_df, "T_Distillate_F", "Distillate Temperature", y_unit="F")
        with row3[1]:
            st.subheader("Distillate Drum Pressure")
            _trend_chart(trends_df, "P_top_drum_psia", "Distillate Drum Pressure", y_unit="psia")

        row4 = st.columns(3)
        with row4[0]:
            st.subheader("Reboiler Duty")
            _trend_chart(trends_df, "Q_reb_used_BTUph", "Reboiler Duty", y_unit="Btu/h")
        with row4[1]:
            st.subheader("Bottoms Sump Level")
            _trend_chart(trends_df, "Bottom_level_fraction", "Bottoms Sump Level", y_unit="fraction (-)")
        with row4[2]:
            st.subheader("Bottoms Controller Output")
            _trend_chart(trends_df, "B_lbmolph", "Bottoms Level Controller Output", y_unit="lbmol/h")

        row5 = st.columns(3)
        with row5[0]:
            st.subheader("Bottoms Flow")
            _trend_chart(trends_df, "B_lbmolph", "Bottoms Flow", y_unit="lbmol/h")
        with row5[1]:
            st.subheader("Bottoms Temperature")
            _trend_chart(trends_df, "T_sump_F", "Bottoms Temperature", y_unit="F")
        with row5[2]:
            st.subheader("Bottoms Composition")
            _trend_chart(trends_df, bottoms_comp_cols, "Bottoms Composition", y_unit="mole fraction (-)")
            _render_composition_change_table(trends_df, bottoms_comp_cols)

        st.subheader("Steady-State Score")
        _trend_chart(trends_df, "steady_state_score", "Steady-State Score", exclude_time_zero=True)

    with tabs[2]:
        _stage_profile_panel(
            snapshot,
            component_names=component_names,
            pressure_profile_psia=list(overview.get("pressure_profile_psia", []) or []),
        )

    with tabs[3]:
        if not overview:
            st.info("Need workbook context to render schematic.")
        else:
            stage_rows = snapshot.to_dict(orient="records") if not snapshot.empty else []
            html = build_column_schematic_html(
                overview=overview,
                summary_row=summary_row or None,
                stage_rows=stage_rows,
            )
            schematic_height = max(980, 520 + 24 * int(overview.get("n_stages") or 0))
            components.html(html, height=schematic_height, scrolling=False)

    with tabs[4]:
        preview_cfg: Dict[str, Any] = {}
        if preview_spec is not None:
            preview_cmd = list(getattr(preview_spec, "command", []) or [])
            preview_cfg = {
                "Run Name": getattr(preview_spec, "run_name", ""),
                "Run Description": getattr(preview_spec, "run_description", ""),
                "Initial State Mode": getattr(preview_spec, "initialization_mode", ""),
                "Stored State": str(getattr(preview_spec, "checkpoint_path", "") or ""),
                "Stored State Schema": getattr(preview_spec, "checkpoint_schema", "") or "",
                "Excel Path": str(getattr(preview_spec, "excel_path", "")),
                "Logs Dir": str(getattr(preview_spec, "logs_dir", "")),
                "Runtime Mode": getattr(preview_spec, "runtime_mode", ""),
                "Thermo Mode": getattr(preview_spec, "thermo_mode", ""),
                "DWSIM Property Package": getattr(preview_spec, "dwsim_property_package", ""),
                "Thermo Table": str(getattr(preview_spec, "thermo_table_path", "") or ""),
                "Table Anchor Blend Count": getattr(preview_spec, "thermo_table_anchor_blend_count", ""),
                "Pool Workers": getattr(preview_spec, "thermo_pool_workers", ""),
                "Pool Chunk Size": getattr(preview_spec, "thermo_pool_chunk_size", ""),
                "Thermo Every N Steps": getattr(preview_spec, "thermo_every_n_steps", ""),
                "Fast Startup": "TRUE" if getattr(preview_spec, "fast_startup_override", False) else "",
                "Eq-Relax Live PR": "TRUE" if getattr(preview_spec, "equilibrium_relaxation_live_pr_override", False) else "",
                "Include Energy": "TRUE" if getattr(preview_spec, "include_energy_override", False) else "",
                "Integrator": getattr(preview_spec, "integrator", ""),
                "n_steps": getattr(preview_spec, "n_steps", ""),
                "dt_sec": getattr(preview_spec, "dt_sec", ""),
                "log_every_n_steps": getattr(preview_spec, "log_every_n_steps", ""),
                "Command Preview": " ".join(str(x) for x in preview_cmd),
            }
        specs_raw = dict(preview_overview.get("specs_raw", {}) or {})
        effective_rows = _effective_config_rows(preview_spec, specs_raw)
        active_cfg = {
            "Run Name": active.get("run_name", ""),
            "Run Description": active.get("run_description", ""),
            "Initial State Mode": active.get("initialization_mode", "fresh"),
            "Stored State": active.get("checkpoint_path", ""),
            "Stored State Schema": active.get("checkpoint_schema", ""),
            "Excel Path": active.get("excel_path", ""),
            "Logs Dir": active.get("logs_dir", ""),
            "Restart Workbook": run_metadata.get("restart_workbook", ""),
            "Runtime Mode": _command_option_value(active.get("command", []), "--runtime-mode"),
            "Thermo Mode": _command_option_value(active.get("command", []), "--thermo"),
            "DWSIM Property Package": _command_option_value(active.get("command", []), "--dwsim-property-package"),
            "Thermo Table": _command_option_value(active.get("command", []), "--thermo-table"),
            "Table Anchor Blend Count": _command_option_value(active.get("command", []), "--thermo-table-anchor-blend-count"),
            "Pool Workers": _command_option_value(active.get("command", []), "--thermo-pool-workers"),
            "Pool Chunk Size": _command_option_value(active.get("command", []), "--thermo-pool-chunk-size"),
            "Thermo Every N Steps": _command_option_value(active.get("command", []), "--thermo-every"),
            "Fast Startup": "TRUE" if active.get("command") and "--fast-startup" in active.get("command", []) else "",
            "Eq-Relax Live PR": "TRUE" if active.get("command") and "--equilibrium-relaxation-live-pr" in active.get("command", []) else "",
            "Include Energy": "TRUE" if active.get("command") and "--include-energy" in active.get("command", []) else "",
            "Integrator": _command_option_value(active.get("command", []), "--integrator"),
            "n_steps": active.get("n_steps", ""),
            "dt_sec": active.get("dt_sec", ""),
            "log_every_n_steps": active.get("log_every_n_steps", ""),
        }
        st.markdown("#### Effective Run Parameters")
        st.dataframe(pd.DataFrame(effective_rows), use_container_width=True, height=520)
        st.markdown("#### Selected Input / Pending Launch")
        if preview_cfg:
            st.dataframe(_config_table_from_mapping(preview_cfg), use_container_width=True, height=360)
        else:
            st.info("Select or upload an Excel input to preview workbook-driven configuration.")
        st.markdown("#### Workbook Specifications")
        if specs_raw:
            st.dataframe(_config_table_from_mapping(specs_raw), use_container_width=True, height=520)
        else:
            st.info("No workbook specifications available.")
        st.markdown("#### Input Validation")
        if preview_validation:
            if preview_validation.get("errors"):
                st.error("\n".join(str(x) for x in preview_validation.get("errors", [])))
            else:
                st.success("No blocking input errors found.")
            if preview_validation.get("warnings"):
                st.warning("\n".join(str(x) for x in preview_validation.get("warnings", [])))
            else:
                st.info("No input warnings.")
        else:
            st.info("Click `Validate Inputs` to run a preflight check on the current workbook.")
        st.markdown("#### Active Run Settings")
        if active.get("command"):
            st.dataframe(_config_table_from_mapping(active_cfg), use_container_width=True, height=320)
        else:
            st.info("No active run settings yet.")

    with tabs[5]:
        if not logs_dir:
            st.info("No active run.")
        else:
            stdout_log = Path(str(active.get("stdout_log", "")))
            stderr_log = Path(str(active.get("stderr_log", "")))
            warnings = extract_warning_lines(stdout_log) + extract_warning_lines(stderr_log)
            if warnings:
                st.warning("\n".join(warnings[-20:]))
            else:
                st.success("No warnings surfaced yet.")
            if phase_info.get("latest_milestone"):
                st.markdown("#### Latest Startup Milestone")
                st.code(str(phase_info.get("latest_milestone")), language="text")
            if phase_info.get("latest_progress"):
                st.markdown("#### Latest Progress Line")
                st.code(str(phase_info.get("latest_progress")), language="text")
            st.markdown("#### Run Description")
            st.write(active.get("run_description", "") or "n/a")


def main() -> None:
    st.set_page_config(page_title="Dynamic Distillation UI", layout="wide")
    st.title("Dynamic Distillation Simulator")

    active_pre = active_run_status(read_active_run())
    if bool(st.session_state.get("_request_clear_ui", False)):
        _reset_form_state(include_launch_mode=False)
        if not active_pre.get("is_running", False):
            clear_active_run()
        st.session_state["_request_clear_ui"] = False
        st.session_state["_clear_ui_flash"] = "Inputs cleared."
        st.rerun()
    if bool(st.session_state.pop("_request_reset_ui", False)):
        if active_pre.get("pid"):
            terminate_pid(int(active_pre["pid"]))
        clear_active_run()
        _reset_form_state()
        st.session_state["_reset_ui_flash"] = "UI reset."
        st.rerun()
    clear_flash = str(st.session_state.pop("_clear_ui_flash", "") or "").strip()
    if clear_flash:
        st.success(clear_flash)
    reset_flash = str(st.session_state.pop("_reset_ui_flash", "") or "").strip()
    if reset_flash:
        st.success(reset_flash)

    refresh_sec = st.sidebar.selectbox("Auto refresh (sec)", options=[0, 2, 5, 10], index=2, key="auto_refresh_sec")
    st.sidebar.caption("Updates live charts and status only; form inputs are preserved.")
    st.sidebar.slider(
        "Startup panel height",
        min_value=180,
        max_value=700,
        value=int(st.session_state.get("startup_panel_height_px", 320) or 320),
        step=20,
        key="startup_panel_height_px",
        help="Adjust the height of the scrollable startup detail frame in the Progress tab.",
    )
    launch_mode = st.sidebar.selectbox("Launch Mode", options=["Form", "CLI"], index=0, key="launch_mode")
    initialization_choice = st.sidebar.radio(
        "Initial State",
        options=["Fresh Start from Excel", "Restart from Stored State"],
        key="initialization_mode",
        help="A restart still uses Excel for the case definition and configuration.",
    )
    initialization_mode = "restart" if initialization_choice.startswith("Restart") else "fresh"
    stored_state_path: Optional[Path] = None
    stored_state_info: Dict[str, Any] = {}
    stored_state_error = ""

    excel_path = _current_excel_selection()
    if initialization_mode == "restart":
        stored_state_path = _current_stored_state_selection()
        if stored_state_path is None:
            stored_state_error = "Select or upload a stored-state checkpoint."
        else:
            try:
                stored_state_info = inspect_stored_state(stored_state_path)
                if not stored_state_info.get("compatible"):
                    stored_state_error = str(stored_state_info.get("reason") or "Stored state is incompatible.")
            except Exception as exc:
                stored_state_error = str(exc)
    core_v3_restart = bool(
        initialization_mode == "restart"
        and stored_state_info.get("schema") == "dynamic_distillation.core_v3_checkpoint.v1"
    )
    if "input_validation_report" not in st.session_state:
        st.session_state["input_validation_report"] = {}
    if "input_validation_excel_path" not in st.session_state:
        st.session_state["input_validation_excel_path"] = ""
    run_name = str(st.session_state.get("run_name", "") or "")
    run_description = str(st.session_state.get("run_description", "") or "")
    runtime_mode = str(st.session_state.get("runtime_mode_override", "hydraulic") or "hydraulic")
    thermo_mode = str(st.session_state.get("thermo_mode_override", "table-pool") or "table-pool")
    dwsim_property_package = str(st.session_state.get("dwsim_property_package_override", "pr") or "pr")
    thermo_pool_workers = int(st.session_state.get("thermo_pool_workers_override", 2) or 2)
    thermo_pool_chunk_size = int(st.session_state.get("thermo_pool_chunk_size_override", 4) or 4)
    thermo_every_n_steps = int(st.session_state.get("thermo_every_override", 1) or 1)
    fast_startup_choice = str(st.session_state.get("fast_startup_override", "Off") or "Off")
    thermo_table_anchor_blend_count = int(st.session_state.get("thermo_anchor_blend_count_override", 3) or 3)
    equilibrium_relaxation_live_pr_choice = str(
        st.session_state.get("equilibrium_relaxation_live_pr_override", "Off") or "Off"
    )
    integrator = str(st.session_state.get("integrator_override", "explicit-euler") or "explicit-euler")
    include_energy_choice = str(st.session_state.get("include_energy_override", "Off") or "Off")
    core_v3_duration_sec = float(st.session_state.get("core_v3_duration_sec", 30.0) or 30.0)
    core_v3_log_every_n_steps = int(st.session_state.get("core_v3_log_every_n_steps", 4) or 4)

    cli_command_text = str(st.session_state.get("cli_command_text", "") or "")

    if launch_mode == "Form":
        run_name = st.sidebar.text_input("Run Name", value=run_name, key="run_name")
        run_description = st.sidebar.text_area("Run Description", value=run_description, height=100, key="run_description")
        if core_v3_restart:
            st.sidebar.markdown("### Core V3 Run")
            core_v3_duration_sec = float(
                st.sidebar.number_input(
                    "Simulation Duration (sec)",
                    min_value=0.25,
                    max_value=86400.0,
                    value=30.0,
                    step=0.25,
                    key="core_v3_duration_sec",
                )
            )
            core_v3_log_every_n_steps = int(
                st.sidebar.number_input(
                    "Log Every N Steps",
                    min_value=1,
                    max_value=10000,
                    value=4,
                    step=1,
                    key="core_v3_log_every_n_steps",
                )
            )
            st.sidebar.caption(
                "Core V3 implicit timestep: 0.25 s. Thermodynamics: live DWSIM "
                "Peng-Robinson. Jacobian: 8 persistent workers."
            )
        else:
            with st.sidebar.expander("Advanced Run Overrides", expanded=False):
                st.caption("UI override > workbook-supported Excel setting > runner default")
                runtime_mode = st.selectbox(
                    "Runtime Mode",
                    options=["hydraulic", "legacy", "parity", "calibration"],
                    index=0,
                    key="runtime_mode_override",
                    help="UI default is hydraulic. Underlying runner fallback is legacy.",
                )
                thermo_mode = st.selectbox(
                    "Thermo Mode",
                    options=["table-pool", "table", "relative-volatility", "dwsim", "stub"],
                    index=0,
                    key="thermo_mode_override",
                )
                if thermo_mode == "dwsim":
                    dwsim_property_package = st.selectbox(
                        "DWSIM Property Package",
                        options=["pr", "srk", "unifac", "nrtl", "uniquac", "raoult"],
                        index=0,
                        key="dwsim_property_package_override",
                        help="Choose the DWSIM property package used for live DWSIM thermo.",
                    )
                if thermo_mode in {"table", "table-pool"}:
                    thermo_table_options = [""] + [str(p) for p in _discover_thermo_tables()] + ["__custom__"]
                    if "thermo_table_choice_override" not in st.session_state:
                        st.session_state["thermo_table_choice_override"] = ""
                    thermo_table_choice = st.selectbox(
                        "Thermo Table",
                        options=thermo_table_options,
                        key="thermo_table_choice_override",
                        format_func=_thermo_table_option_label,
                        help="Select a discovered thermo table or choose Custom path.",
                    )
                    if thermo_table_choice == "__custom__":
                        st.text_input(
                            "Custom Thermo Table Path",
                            value=str(st.session_state.get("thermo_table_path_override", "") or ""),
                            key="thermo_table_path_override",
                            help="Optional path override for table or table-pool thermo.",
                        )
                    else:
                        st.session_state["thermo_table_path_override"] = ""
                pool_c1, pool_c2 = st.columns(2)
                with pool_c1:
                    thermo_pool_workers = st.number_input(
                        "Pool Workers",
                        min_value=1,
                        max_value=64,
                        value=2,
                        step=1,
                        key="thermo_pool_workers_override",
                        help="Runner default is 2.",
                    )
                with pool_c2:
                    thermo_pool_chunk_size = st.number_input(
                        "Pool Chunk",
                        min_value=1,
                        max_value=128,
                        value=4,
                        step=1,
                        key="thermo_pool_chunk_size_override",
                        help="Runner default is 4.",
                    )
                thermo_every_n_steps = st.number_input(
                    "Thermo Every N Steps",
                    min_value=1,
                    max_value=1000,
                    value=1,
                    step=1,
                    key="thermo_every_override",
                    help="Runner default is 1.",
                )
                fast_startup_choice = st.selectbox(
                    "Fast Startup",
                    options=["Off", "On"],
                    index=0,
                    key="fast_startup_override",
                    help="Reduce startup conditioning time; best for exploratory runs.",
                )
                thermo_table_anchor_blend_count = st.number_input(
                    "Table Anchor Blend Count",
                    min_value=1,
                    max_value=32,
                    value=3,
                    step=1,
                    key="thermo_anchor_blend_count_override",
                    help="Runner default is 3. Use 6 for the refined-table branch.",
                )
                equilibrium_relaxation_live_pr_choice = st.selectbox(
                    "Eq-Relax Live PR",
                    options=["Off", "On"],
                    index=0,
                    key="equilibrium_relaxation_live_pr_override",
                    help="Runner default is Off.",
                )
                integrator = st.selectbox(
                    "Integrator",
                    options=["explicit-euler", "bdf", "radau", "ida"],
                    index=0,
                    key="integrator_override",
                )
                include_energy_choice = st.selectbox(
                    "Include Energy",
                    options=["Off", "On"],
                    index=0,
                    key="include_energy_override",
                    help="Runner default is Off.",
                )
    else:
        st.sidebar.caption(
            "Paste legacy runner flags, a full legacy command, or a `python tools/run_core_v3_dynamic.py ...` command. "
            "If `--excel` or `--init-from-checkpoint` is omitted, the selected workbook or stored state above is used."
        )
        cli_command_text = st.sidebar.text_area(
            "Runner CLI",
            value=cli_command_text,
            height=180,
            key="cli_command_text",
            placeholder="--runtime-mode hydraulic --include-energy --thermo table-pool",
        )

    active = active_run_status(read_active_run())
    preview_spec = None
    cli_launch_error = ""
    form_launch_error = ""
    selected_thermo_table_path = _selected_thermo_table_path()
    if launch_mode == "Form":
        if excel_path is not None and excel_path.exists():
            try:
                preview_spec = build_launch_spec(
                    excel_path=excel_path,
                    initialization_mode=initialization_mode,
                    checkpoint_path=stored_state_path,
                    run_name=run_name or excel_path.stem,
                    run_description=run_description,
                    runtime_mode=runtime_mode,
                    thermo_mode=thermo_mode,
                    dwsim_property_package=dwsim_property_package,
                    thermo_table_path=Path(selected_thermo_table_path) if selected_thermo_table_path else None,
                    thermo_table_anchor_blend_count=int(thermo_table_anchor_blend_count),
                    thermo_pool_workers=int(thermo_pool_workers),
                    thermo_pool_chunk_size=int(thermo_pool_chunk_size),
                    thermo_every_n_steps=int(thermo_every_n_steps),
                    fast_startup_override=(True if fast_startup_choice == "On" else None),
                    equilibrium_relaxation_live_pr_override=(True if equilibrium_relaxation_live_pr_choice == "On" else None),
                    include_energy_override=True if include_energy_choice == "On" else None,
                    integrator=integrator,
                    core_v3_duration_sec=core_v3_duration_sec,
                    core_v3_log_every_n_steps=core_v3_log_every_n_steps,
                )
            except Exception as exc:
                preview_spec = None
                form_launch_error = str(exc)
    else:
        cli_text_clean = str(cli_command_text or "").strip()
        if cli_text_clean:
            try:
                preview_spec = build_launch_spec_from_cli(
                    cli_text_clean,
                    default_excel_path=excel_path,
                    initialization_mode=initialization_mode,
                    default_checkpoint_path=stored_state_path,
                )
            except Exception as exc:
                cli_launch_error = str(exc)

    validation_excel_path = preview_spec.excel_path if preview_spec is not None else excel_path
    current_excel_key = (
        str(validation_excel_path.resolve()) if validation_excel_path is not None and validation_excel_path.exists() else ""
    )
    if st.session_state.get("input_validation_excel_path", "") != current_excel_key:
        _clear_validation_state()
    input_validation: Dict[str, Any] = dict(st.session_state.get("input_validation_report", {}) or {})

    with st.sidebar:
        if launch_mode == "CLI":
            if stored_state_error:
                st.error(stored_state_error)
            elif cli_launch_error:
                st.error(cli_launch_error)
            elif preview_spec is not None:
                source = "stored state" if preview_spec.initialization_mode == "restart" else "Excel seed"
                st.info(f"CLI initial state: {source}.")
        elif initialization_mode == "restart":
            if stored_state_error or form_launch_error:
                st.error(stored_state_error or form_launch_error)
            elif stored_state_info:
                final_time = stored_state_info.get("final_time_s")
                time_text = "unknown time" if final_time is None else f"t={float(final_time):g} s"
                checkpoint_label = "Core V3 checkpoint" if core_v3_restart else "Legacy checkpoint"
                st.success(f"{checkpoint_label} accepted ({time_text}).")
        if validation_excel_path is not None and validation_excel_path.exists():
            if input_validation:
                if input_validation.get("errors"):
                    st.error("Input check: blocking errors found.")
                elif input_validation.get("warnings"):
                    st.warning(f"Input check: {len(input_validation.get('warnings', []))} warning(s).")
                else:
                    st.success("Input check passed.")
            else:
                st.info("Input check not yet run for current workbook.")
        st.markdown("### Run Control")
        validate_disabled = validation_excel_path is None or (launch_mode == "CLI" and preview_spec is None)
        validate_clicked = st.button("Validate Inputs", disabled=validate_disabled)
        if active.get("status") == "paused":
            start_label = "Resume Paused Run"
        elif launch_mode == "CLI":
            start_label = "Run CLI Command"
        elif launch_mode == "Form" and initialization_mode == "restart":
            start_label = "Start Core V3 Run" if core_v3_restart else "Start Restart Run"
        else:
            start_label = "Start Fresh Run"
        start_disabled = False
        if active.get("status") == "running":
            start_disabled = True
        elif active.get("status") != "paused" and validation_excel_path is None:
            start_disabled = True
        elif active.get("status") != "paused" and launch_mode == "CLI" and preview_spec is None:
            start_disabled = True
        elif active.get("status") != "paused" and launch_mode == "Form" and preview_spec is None:
            start_disabled = True
        elif active.get("status") != "paused" and bool(input_validation) and bool(input_validation.get("errors")):
            start_disabled = True
        start_clicked = st.button(start_label, type="primary", disabled=start_disabled)
        if start_disabled and active.get("status") != "running":
            if launch_mode == "CLI" and (stored_state_error or cli_launch_error):
                st.caption(f"Run unavailable: {stored_state_error or cli_launch_error}")
            elif launch_mode == "Form" and form_launch_error:
                st.caption(f"Run unavailable: {form_launch_error}")
        pause_clicked = st.button("Pause Simulation", disabled=active.get("status") != "running")
        stop_clicked = st.button("Stop Simulation", disabled=active.get("status") not in {"running", "paused"})
        add_time_sec = int(
            st.number_input(
                "Add Time (sec)",
                min_value=1,
                max_value=86400,
                value=int(st.session_state.get("add_time_seconds", 60) or 60),
                step=10,
                key="add_time_seconds",
                help="Extend the active simulation horizon by this many seconds.",
            )
        )
        add_time_clicked = st.button(
            "Add Time",
            disabled=active.get("status") not in {"running", "paused"},
        )
        clear_clicked = st.button("Clear")
        st.caption("Clears entered fields; does not stop a running simulation or change launch mode.")
        reset_clicked = st.button("Reset UI")
        st.caption("Stops the active simulation, clears saved run state, and resets the dashboard.")

    if clear_clicked:
        _request_clear_ui()
        st.rerun()

    if reset_clicked:
        _request_reset_ui()
        st.rerun()

    if validate_clicked and validation_excel_path is not None and validation_excel_path.exists():
        report = validate_excel_input(validation_excel_path)
        st.session_state["input_validation_report"] = dict(report or {})
        st.session_state["input_validation_excel_path"] = current_excel_key
        if report.get("errors"):
            st.error("Input validation found blocking errors.")
        elif report.get("warnings"):
            st.warning(f"Input validation completed with {len(report.get('warnings', []))} warning(s).")
        else:
            st.success("Input validation passed.")
        st.rerun()

    if start_clicked and active.get("status") == "paused" and active.get("pid"):
        ok = resume_pid(int(active["pid"]))
        if ok:
            update_active_run(paused=False, resumed_at_local=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            st.success("Simulation resumed.")
        else:
            st.error("Failed to resume the simulation process.")
        st.rerun()

    if pause_clicked and active.get("status") == "running" and active.get("pid"):
        ok = suspend_pid(int(active["pid"]))
        if ok:
            update_active_run(paused=True, paused_at_local=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            st.warning("Simulation paused.")
        else:
            st.error("Failed to pause the simulation process.")
        st.rerun()

    if add_time_clicked and active.get("status") in {"running", "paused"}:
        try:
            dt_sec = float(active.get("dt_sec"))
            current_n_steps = int(active.get("n_steps"))
            add_steps = max(1, int(round(float(add_time_sec) / max(dt_sec, 1.0e-12))))
            new_n_steps = int(current_n_steps + add_steps)
            request_runtime_extension(
                logs_dir=Path(str(active.get("logs_dir"))),
                requested_total_steps=new_n_steps,
                dt_sec=float(dt_sec),
            )
            update_active_run(n_steps=int(new_n_steps))
            actual_added_sec = float(add_steps) * float(dt_sec)
            st.success(f"Added {actual_added_sec:.1f} s to the simulation horizon.")
        except Exception as exc:
            st.error(f"Failed to extend simulation time: {exc}")
        st.rerun()

    if start_clicked and active.get("status") != "paused":
        spec = preview_spec
        if spec is None and launch_mode == "Form" and excel_path is not None:
            spec = build_launch_spec(
                excel_path=excel_path,
                initialization_mode=initialization_mode,
                checkpoint_path=stored_state_path,
                run_name=run_name or excel_path.stem,
                run_description=run_description,
                runtime_mode=runtime_mode,
                thermo_mode=thermo_mode,
                dwsim_property_package=dwsim_property_package,
                thermo_table_path=Path(selected_thermo_table_path) if selected_thermo_table_path else None,
                thermo_table_anchor_blend_count=int(thermo_table_anchor_blend_count),
                thermo_pool_workers=int(thermo_pool_workers),
                thermo_pool_chunk_size=int(thermo_pool_chunk_size),
                thermo_every_n_steps=int(thermo_every_n_steps),
                fast_startup_override=(True if fast_startup_choice == "On" else None),
                equilibrium_relaxation_live_pr_override=(True if equilibrium_relaxation_live_pr_choice == "On" else None),
                include_energy_override=True if include_energy_choice == "On" else None,
                integrator=integrator,
                core_v3_duration_sec=core_v3_duration_sec,
                core_v3_log_every_n_steps=core_v3_log_every_n_steps,
            )
        if spec is None:
            st.error("No valid launch specification is available.")
            st.stop()
        launch_info = launch_simulation(spec)
        active = active_run_status(launch_info)
        st.success(f"Started run `{spec.run_name}` in {spec.logs_dir}")
        st.rerun()

    if stop_clicked and active.get("pid"):
        ok = terminate_pid(int(active["pid"]))
        active = active_run_status(read_active_run())
        if ok:
            st.warning("Stop signal sent to simulation process.")
        else:
            st.error("Failed to stop the simulation process.")
        st.rerun()

    run_every = None
    if active.get("is_running") and int(refresh_sec) > 0:
        run_every = f"{int(refresh_sec)}s"

    fragment_fn = getattr(st, "fragment", None)
    if callable(fragment_fn):
        @fragment_fn(run_every=run_every)
        def _live_fragment() -> None:
            _render_live_dashboard(
                selected_excel_path=validation_excel_path,
                preview_spec=preview_spec,
            )

        _live_fragment()
    else:
        if active.get("is_running") and int(refresh_sec) > 0:
            st.info(
                "Built-in auto refresh is not available in this Streamlit runtime. "
                "Using browser reload fallback while the simulation is running."
            )
            _render_browser_autorefresh(int(refresh_sec))
        _render_live_dashboard(
            selected_excel_path=validation_excel_path,
            preview_spec=preview_spec,
        )


if __name__ == "__main__":
    main()
