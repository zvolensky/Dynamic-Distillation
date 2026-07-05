#!/usr/bin/env python
"""
Column initialization residual audit.

Evaluate column_rhs once at the initialized state and rank the residuals that
would immediately move the model away from an imported steady-state seed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import math
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import ColumnInputs, column_rhs  # noqa: E402
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_vapor_holdup_from_spec_pressure,
    build_inputs_for_runner,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_path(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _finite_float(value: Any, default: float = math.nan) -> float:
    try:
        v = float(value)
    except Exception:
        return default
    return v if np.isfinite(v) else default


def _diag_scalar(diag: Dict[str, Any], key: str) -> float:
    if key not in diag:
        return math.nan
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((-1,))
    except Exception:
        return math.nan
    if arr.size == 0:
        return math.nan
    return _finite_float(arr[0])


def _component_names(col: Any) -> List[str]:
    names = [str(v) for v in getattr(col, "components_excel", [])]
    if names:
        return names
    return [f"component_{i + 1}" for i in range(int(col.n_components))]


def _build_initial_state(
    *,
    col: Any,
    layout: StateVectorLayout,
    inputs: ColumnInputs,
    include_temperature: bool,
    use_excel_vapor_holdup: bool,
) -> np.ndarray:
    y = layout.pack_y0(col)
    if not bool(use_excel_vapor_holdup):
        y = _clear_initial_tray_vapor_holdup(y, layout)
    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=inputs,
        include_temperature=bool(include_temperature),
        preserve_tray_vapor_holdup=bool(use_excel_vapor_holdup),
    )
    return np.asarray(y, dtype=float)


def _iter_state_rows(
    *,
    block: str,
    values: np.ndarray,
    rates: np.ndarray,
    component_names: List[str],
    n_stages: int,
    denom_floor_lbmol: float,
) -> Iterable[Dict[str, Any]]:
    vals = np.asarray(values, dtype=float)
    dr = np.asarray(rates, dtype=float)
    if vals.shape != dr.shape:
        return

    if vals.ndim == 2:
        for i in range(vals.shape[0]):
            for k in range(vals.shape[1]):
                inv = float(vals[i, k])
                rate = float(dr[i, k])
                denom = max(abs(inv) + max(float(denom_floor_lbmol), 0.0), 1.0e-300)
                yield {
                    "state_block": block,
                    "stage_1based": int(i + 1),
                    "component_1based": int(k + 1),
                    "component_name": component_names[k] if k < len(component_names) else f"component_{k + 1}",
                    "inventory": inv,
                    "rate_per_s": rate,
                    "rate_per_h": rate * 3600.0,
                    "relative_rate_per_s": abs(rate) / denom,
                    "denominator": denom,
                }
    elif vals.ndim == 1:
        for idx in range(vals.size):
            inv = float(vals[idx])
            rate = float(dr[idx])
            if block.startswith("tray_"):
                stage = int(idx + 1)
                comp = ""
                comp_idx: Any = ""
            elif block.startswith("top_"):
                stage = 0
                comp_idx = int(idx + 1)
                comp = component_names[idx] if idx < len(component_names) else f"component_{idx + 1}"
            elif block.startswith("bottom_"):
                stage = int(n_stages + 1)
                comp_idx = int(idx + 1)
                comp = component_names[idx] if idx < len(component_names) else f"component_{idx + 1}"
            else:
                stage = ""
                comp_idx = ""
                comp = ""
            denom = max(abs(inv) + max(float(denom_floor_lbmol), 0.0), 1.0e-300)
            yield {
                "state_block": block,
                "stage_1based": stage,
                "component_1based": comp_idx,
                "component_name": comp,
                "inventory": inv,
                "rate_per_s": rate,
                "rate_per_h": rate * 3600.0,
                "relative_rate_per_s": abs(rate) / denom,
                "denominator": denom,
            }


def _block_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for block in sorted({str(r["state_block"]) for r in rows}):
        b = [r for r in rows if str(r["state_block"]) == block]
        if not b:
            continue
        worst = max(b, key=lambda r: abs(float(r["relative_rate_per_s"])))
        out.append(
            {
                "state_block": block,
                "max_abs_rate_per_s": max(abs(float(r["rate_per_s"])) for r in b),
                "max_abs_rate_per_h": max(abs(float(r["rate_per_h"])) for r in b),
                "max_relative_rate_per_s": float(worst["relative_rate_per_s"]),
                "worst_stage_1based": worst["stage_1based"],
                "worst_component_1based": worst["component_1based"],
                "worst_component_name": worst["component_name"],
            }
        )
    out.sort(key=lambda r: abs(float(r["max_relative_rate_per_s"])), reverse=True)
    return out


def _phase_total_rows(du: Dict[str, Any], n_stages: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(n_stages):
        l_rate = 0.0
        v_rate = 0.0
        if "tray_L" in du:
            l_rate = float(np.sum(np.asarray(du["tray_L"], dtype=float).reshape((n_stages, -1))[i, :]))
        if "tray_V" in du:
            v_rate = float(np.sum(np.asarray(du["tray_V"], dtype=float).reshape((n_stages, -1))[i, :]))
        out.append(
            {
                "stage_1based": int(i + 1),
                "tray_L_total_rate_lbmolps": l_rate,
                "tray_V_total_rate_lbmolps": v_rate,
                "tray_total_rate_lbmolps": l_rate + v_rate,
                "tray_total_rate_lbmolph": (l_rate + v_rate) * 3600.0,
            }
        )
    return out


def _write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _write_markdown(path: Path, summary: Dict[str, Any], top_rows: List[Dict[str, Any]]) -> None:
    lines: List[str] = []
    lines.append("# Column Initialization Residual Audit")
    lines.append("")
    lines.append(f"- Excel: `{summary['excel']}`")
    lines.append(f"- Thermo: `{summary['thermo_mode']}`")
    lines.append(f"- Runtime mode: `{summary['runtime_mode']}`")
    lines.append(f"- Pressure model: `{summary['pressure_model']}`")
    lines.append(f"- Vapor flow model: `{summary['vapor_flow_model']}`")
    lines.append(f"- Equilibrium relaxation: `{summary['equilibrium_relaxation']}`")
    lines.append(f"- Uses Excel vapor holdup: `{summary['use_excel_vapor_holdup']}`")
    lines.append("")
    lines.append("## Gate")
    lines.append("")
    lines.append(f"- Pass: `{summary['gate_pass']}`")
    lines.append(f"- Worst relative state rate: `{summary['max_relative_rate_per_s']:.8g} 1/s`")
    lines.append(f"- Worst absolute state rate: `{summary['max_abs_rate_per_s']:.8g} per s`")
    lines.append(f"- Max tray total material residual: `{summary['max_abs_tray_total_rate_lbmolph']:.8g} lbmol/h`")
    lines.append(f"- Total state inventory residual: `{summary['total_state_inventory_rate_lbmolph']:.8g} lbmol/h`")
    lines.append("")
    if "diag_total_condenser_boundary_energy_residual_BTUps" in summary:
        lines.append("## Top Boundary Diagnostics")
        lines.append("")
        lines.append(
            "- Total condenser boundary energy residual: "
            f"`{summary['diag_total_condenser_boundary_energy_residual_BTUps']:.8g} Btu/s`"
        )
        lines.append(
            "- Total condenser boundary energy residual relative scale: "
            f"`{summary['diag_total_condenser_boundary_energy_residual_rel']:.8g}`"
        )
        lines.append(
            "- Total condenser boundary energy owner: "
            f"`{summary['diag_total_condenser_boundary_energy_owner']:.8g}`"
        )
        lines.append("")
    lines.append("## Block Ranking")
    lines.append("")
    lines.append("| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |")
    lines.append("|---|---:|---:|---:|---|")
    for row in summary["block_summary"]:
        lines.append(
            f"| `{row['state_block']}` | {float(row['max_relative_rate_per_s']):.8g} | "
            f"{float(row['max_abs_rate_per_s']):.8g} | {row['worst_stage_1based']} | "
            f"{row['worst_component_name']} |"
        )
    lines.append("")
    lines.append("## Worst State Rows")
    lines.append("")
    lines.append("| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |")
    lines.append("|---:|---|---:|---|---:|---:|---:|")
    for rank, row in enumerate(top_rows[:20], start=1):
        lines.append(
            f"| {rank} | `{row['state_block']}` | {row['stage_1based']} | "
            f"{row['component_name']} | {float(row['rate_per_s']):.8g} | "
            f"{float(row['relative_rate_per_s']):.8g} | {float(row['inventory']):.8g} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit t=0 dynamic consistency of a column initialization seed.")
    ap.add_argument("--excel", required=True, help="Input workbook to audit.")
    ap.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["stub", "relative-volatility", "simple-rv", "constant-alpha", "clapeyron", "table", "table-pool", "dwsim"],
        default="clapeyron",
    )
    ap.add_argument("--clapeyron-model", default="PR")
    ap.add_argument("--dwsim-property-package", default="pr")
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--runtime-mode", choices=["legacy", "parity", "calibration", "hydraulic"], default="parity")
    ap.add_argument("--condenser-duty-mode", default="total-condense")
    ap.add_argument("--condenser-duty-btuph", type=float, default=None)
    ap.add_argument("--scenario", choices=["default", "spec_profile_no_feed_flash", "spec_profile_with_feed_flash"], default="default")
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-energy", dest="include_energy", action="store_false")
    ap.set_defaults(include_temperature=True, include_energy=False)
    ap.add_argument("--disable-boundary-states", dest="include_boundary_states", action="store_false")
    ap.set_defaults(include_boundary_states=True)
    ap.add_argument("--disable-vapor-states", dest="include_vapor_states", action="store_false")
    ap.set_defaults(include_vapor_states=True)
    ap.add_argument("--use-excel-vapor-holdup", action="store_true")
    ap.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    ap.set_defaults(enable_equilibrium_relaxation=True)
    ap.add_argument("--no-flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_false")
    ap.add_argument("--flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_true")
    ap.set_defaults(flash_feed_at_stage_conditions=None)
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=None)
    ap.add_argument("--debug-freeze-tray-vapor-derivatives", action="store_true")
    ap.add_argument("--debug-override-reflux-composition", action="store_true")
    ap.add_argument("--debug-clamp-top-drum-pressure-psia", type=float, default=None)
    ap.add_argument("--denom-floor-lbmol", type=float, default=1.0)
    ap.add_argument("--relative-rate-gate", type=float, default=1.0e-4)
    ap.add_argument("--tray-total-rate-gate-lbmolph", type=float, default=1.0)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    excel_path = _resolve_path(args.excel)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo_mode).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(args.thermo_table_path)
        if not thermo_table_path.exists():
            raise FileNotFoundError(f"Thermo table file not found: {thermo_table_path}")

    tag = _timestamp_tag()
    output_dir = _resolve_path(args.output_dir) if args.output_dir else (
        _PROJECT_ROOT / "logs" / "initialization_audits" / tag
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
        include_top=bool(args.include_boundary_states),
        include_bottom=bool(args.include_boundary_states),
        include_vapor=bool(args.include_vapor_states),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
    )

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode=str(args.runtime_mode),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        include_boundary_states=bool(args.include_boundary_states),
        include_vapor_states=bool(args.include_vapor_states),
        thermo_mode=str(args.thermo_mode),
        clapeyron_model=str(args.clapeyron_model),
        dwsim_property_package=str(args.dwsim_property_package),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        condenser_duty_mode=str(args.condenser_duty_mode),
        condenser_duty_btu_per_h=args.condenser_duty_btuph,
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        flash_feed_at_stage_conditions=args.flash_feed_at_stage_conditions,
        vapor_holdup_relaxation_sec=args.vapor_holdup_relaxation_sec,
        debug_freeze_tray_vapor_derivatives=bool(args.debug_freeze_tray_vapor_derivatives),
        debug_override_reflux_composition=bool(args.debug_override_reflux_composition),
        debug_clamp_top_drum_pressure_psia=args.debug_clamp_top_drum_pressure_psia,
        write_logs=False,
    )

    base_inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        inputs = base_inputs
        if args.scenario == "spec_profile_no_feed_flash":
            inputs = replace(inputs, pressure_model="spec", vapor_flow_model="profile", flash_feed_at_stage_conditions=False)
        elif args.scenario == "spec_profile_with_feed_flash":
            inputs = replace(inputs, pressure_model="spec", vapor_flow_model="profile", flash_feed_at_stage_conditions=True)

        y0 = _build_initial_state(
            col=col,
            layout=layout,
            inputs=inputs,
            include_temperature=bool(args.include_temperature),
            use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
        )
        dydt, diag = column_rhs(0.0, y0, col, layout, inputs)
        u = layout.unpack(y0)
        du = layout.unpack(np.asarray(dydt, dtype=float))

        names = _component_names(col)
        rows: List[Dict[str, Any]] = []
        for block in (
            "tray_L",
            "tray_V",
            "top_L",
            "top_V",
            "bottom_L",
            "bottom_V",
            "tray_T_f",
            "bottom_T_f",
            "tray_EL_BTU",
            "tray_EV_BTU",
        ):
            if block not in u or block not in du:
                continue
            rows.extend(
                _iter_state_rows(
                    block=block,
                    values=np.asarray(u[block], dtype=float),
                    rates=np.asarray(du[block], dtype=float),
                    component_names=names,
                    n_stages=int(col.n_stages),
                    denom_floor_lbmol=float(args.denom_floor_lbmol),
                )
            )

        rows.sort(key=lambda r: abs(float(r["relative_rate_per_s"])), reverse=True)
        for i, row in enumerate(rows, start=1):
            row["rank"] = i

        phase_rows = _phase_total_rows(du, int(col.n_stages))
        block_rows = _block_summary(rows)
        max_rel = max((abs(float(r["relative_rate_per_s"])) for r in rows), default=0.0)
        max_abs_rate = max((abs(float(r["rate_per_s"])) for r in rows), default=0.0)
        max_tray_total_ph = max((abs(float(r["tray_total_rate_lbmolph"])) for r in phase_rows), default=0.0)

        total_state_rate_ph = 0.0
        for key in ("tray_L", "tray_V", "top_L", "top_V", "bottom_L", "bottom_V"):
            if key in du:
                total_state_rate_ph += float(np.sum(np.asarray(du[key], dtype=float))) * 3600.0

        gate_pass = bool(
            max_rel <= float(args.relative_rate_gate)
            and max_tray_total_ph <= float(args.tray_total_rate_gate_lbmolph)
        )

        summary: Dict[str, Any] = {
            "excel": str(excel_path),
            "thermo_mode": str(args.thermo_mode),
            "clapeyron_model": str(args.clapeyron_model),
            "runtime_mode": str(args.runtime_mode),
            "scenario": str(args.scenario),
            "pressure_model": str(getattr(inputs, "pressure_model", "")),
            "vapor_flow_model": str(getattr(inputs, "vapor_flow_model", "")),
            "condenser_duty_mode": str(getattr(inputs, "condenser_duty_mode", "")),
            "condenser_duty_btu_per_h": getattr(inputs, "condenser_duty_btu_per_h", None),
            "flash_feed_at_stage_conditions": bool(getattr(inputs, "flash_feed_at_stage_conditions", False)),
            "equilibrium_relaxation": bool(getattr(inputs, "equilibrium_relaxation", False)),
            "vapor_holdup_relaxation_sec": getattr(inputs, "vapor_holdup_relaxation_sec", None),
            "debug_freeze_tray_vapor_derivatives": bool(getattr(inputs, "debug_freeze_tray_vapor_derivatives", False)),
            "debug_override_reflux_composition": bool(getattr(inputs, "debug_override_reflux_composition", False)),
            "debug_clamp_top_drum_pressure_psia": getattr(inputs, "debug_clamp_top_drum_pressure_psia", None),
            "use_excel_vapor_holdup": bool(args.use_excel_vapor_holdup),
            "include_vapor_states": bool(args.include_vapor_states),
            "include_boundary_states": bool(args.include_boundary_states),
            "include_temperature": bool(args.include_temperature),
            "include_energy": bool(args.include_energy),
            "relative_rate_gate": float(args.relative_rate_gate),
            "tray_total_rate_gate_lbmolph": float(args.tray_total_rate_gate_lbmolph),
            "gate_pass": gate_pass,
            "max_relative_rate_per_s": float(max_rel),
            "max_abs_rate_per_s": float(max_abs_rate),
            "max_abs_tray_total_rate_lbmolph": float(max_tray_total_ph),
            "total_state_inventory_rate_lbmolph": float(total_state_rate_ph),
            "diag_dM_total_dt_lbmolph": _diag_scalar(diag, "dM_total_dt_lbmolph"),
            "diag_global_mass_closure_error_lbmolph": _diag_scalar(diag, "global_mass_closure_error_lbmolph"),
            "diag_total_condenser_boundary_energy_residual_BTUps": _diag_scalar(
                diag, "total_condenser_boundary_energy_residual_BTUps"
            ),
            "diag_total_condenser_boundary_energy_residual_rel": _diag_scalar(
                diag, "total_condenser_boundary_energy_residual_rel"
            ),
            "diag_total_condenser_boundary_energy_owner": _diag_scalar(
                diag, "total_condenser_boundary_energy_owner"
            ),
            "debug_freeze_active_diag": _diag_scalar(diag, "debug_freeze_tray_vapor_derivatives_active"),
            "debug_max_orig_dmVdt": _diag_scalar(diag, "debug_max_orig_dmVdt"),
            "debug_max_orig_dmVdt_rel_per_s": _diag_scalar(diag, "debug_max_orig_dmVdt_rel_per_s"),
            "debug_worst_v_stage": _diag_scalar(diag, "debug_worst_v_stage"),
            "debug_worst_v_comp": _diag_scalar(diag, "debug_worst_v_comp"),
            "debug_reflux_overridden": _diag_scalar(diag, "debug_reflux_overridden"),
            "debug_reflux_target_stage": _diag_scalar(diag, "debug_reflux_target_stage"),
            "debug_top_drum_pressure_clamp_active": _diag_scalar(diag, "debug_top_drum_pressure_clamp_active"),
            "debug_top_drum_pressure_clamp_psia": _diag_scalar(diag, "debug_top_drum_pressure_clamp_psia"),
            "debug_top_drum_pressure_clamp_raw_psia": _diag_scalar(diag, "debug_top_drum_pressure_clamp_raw_psia"),
            "debug_reflux_orig_comp2": _diag_scalar(diag, "debug_reflux_orig_comp2"),
            "debug_reflux_target_comp2": _diag_scalar(diag, "debug_reflux_target_comp2"),
            "debug_reflux_comp2_delta": _diag_scalar(diag, "debug_reflux_comp2_delta"),
            "debug_reflux_target_delta_max": _diag_scalar(diag, "debug_reflux_target_delta_max"),
            "block_summary": block_rows,
        }

        state_csv = output_dir / "state_rate_rows.csv"
        stage_csv = output_dir / "stage_phase_total_rates.csv"
        summary_json = output_dir / "summary.json"
        summary_md = output_dir / "summary.md"

        _write_csv(
            state_csv,
            rows,
            [
                "rank",
                "state_block",
                "stage_1based",
                "component_1based",
                "component_name",
                "inventory",
                "rate_per_s",
                "rate_per_h",
                "relative_rate_per_s",
                "denominator",
            ],
        )
        _write_csv(
            stage_csv,
            phase_rows,
            [
                "stage_1based",
                "tray_L_total_rate_lbmolps",
                "tray_V_total_rate_lbmolps",
                "tray_total_rate_lbmolps",
                "tray_total_rate_lbmolph",
            ],
        )
        summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_markdown(summary_md, summary, rows[: max(int(args.top), 1)])

        worst = rows[0] if rows else {}
        print("Column initialization residual audit")
        print(f"Excel: {excel_path}")
        print(f"Output: {output_dir}")
        print(f"Gate pass: {gate_pass}")
        print(f"Max relative state rate: {max_rel:.8g} 1/s")
        print(f"Max tray total residual: {max_tray_total_ph:.8g} lbmol/h")
        if worst:
            print(
                "Worst state: "
                f"{worst['state_block']} stage={worst['stage_1based']} "
                f"component={worst['component_name']} "
                f"rate={float(worst['rate_per_s']):.8g}/s "
                f"rel={float(worst['relative_rate_per_s']):.8g}/s"
            )
        print(f"Wrote: {summary_md}")
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
