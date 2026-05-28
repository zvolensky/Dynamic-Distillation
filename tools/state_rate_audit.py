#!/usr/bin/env python
"""
Rank state-vector rates for a dynamic column restart/input workbook.

This is a focused steady-state debugging aid. It evaluates column_rhs at the
initialized state and reports the largest phase/component rates using the same
relative inventory denominator used by the runner steady-state detector.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
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


def _resolve_path(project_root: Path, raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def _as_float(x: Any, default: float = math.nan) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    return v if np.isfinite(v) else default


def _diag_scalar(diag: Dict[str, Any], key: str) -> float:
    if key not in diag:
        return math.nan
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((-1,))
        if arr.size == 0:
            return math.nan
        return _as_float(arr[0], default=math.nan)
    except Exception:
        return math.nan


def _diag_matrix(diag: Dict[str, Any], key: str, shape: tuple[int, ...]) -> Optional[np.ndarray]:
    if key not in diag:
        return None
    try:
        arr = np.asarray(diag[key], dtype=float).reshape(shape)
    except Exception:
        return None
    return arr


def _scenario_inputs(base_inputs: ColumnInputs, scenario: str) -> ColumnInputs:
    key = str(scenario).strip().lower()
    if key in ("default", "default_from_case"):
        return base_inputs
    if key == "spec_profile_no_feed_flash":
        return replace(
            base_inputs,
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=False,
        )
    if key == "spec_profile_with_feed_flash":
        return replace(
            base_inputs,
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=True,
        )
    if key == "hydraulic_energy_no_feed_flash":
        return replace(
            base_inputs,
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=False,
        )
    if key == "hydraulic_energy_with_feed_flash":
        return replace(
            base_inputs,
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=True,
        )
    raise ValueError(
        f"Unknown scenario '{scenario}'. Use default, spec_profile_no_feed_flash, "
        "spec_profile_with_feed_flash, hydraulic_energy_no_feed_flash, or "
        "hydraulic_energy_with_feed_flash."
    )


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


def _iter_block_rows(
    *,
    state_key: str,
    values: np.ndarray,
    rates: np.ndarray,
    denom_floor_lbmol: float,
    component_names: List[str],
    n_stages: int,
    diag: Dict[str, Any],
) -> Iterable[Dict[str, Any]]:
    vals = np.asarray(values, dtype=float)
    dr = np.asarray(rates, dtype=float)
    if vals.shape != dr.shape:
        return
    floor = max(float(denom_floor_lbmol), 0.0)

    eq_transfer = _diag_matrix(diag, "eq_transfer_lbmolps_tray", (n_stages, len(component_names)))
    y_target = _diag_matrix(diag, "y_target_tray", (n_stages, len(component_names)))
    y_eq = _diag_matrix(diag, "y_eq_tray", (n_stages, len(component_names)))
    k_eq = _diag_matrix(diag, "K_eq_relax_tray", (n_stages, len(component_names)))
    k_state = _diag_matrix(diag, "K_state_y_over_x_tray", (n_stages, len(component_names)))
    k_ratio = _diag_matrix(diag, "K_state_over_K_thermo_tray", (n_stages, len(component_names)))

    if vals.ndim == 2:
        for i in range(vals.shape[0]):
            for k in range(vals.shape[1]):
                inventory = float(vals[i, k])
                rate = float(dr[i, k])
                denom = abs(inventory) + floor
                row = {
                    "state_key": state_key,
                    "stage_1based": int(i + 1),
                    "component_1based": int(k + 1),
                    "component_name": component_names[k] if k < len(component_names) else f"component_{k + 1}",
                    "inventory_lbmol_or_BTU": inventory,
                    "rate_per_s": rate,
                    "rate_lbmolph_or_BTUph": rate * 3600.0,
                    "relative_rate_per_s": abs(rate) / max(denom, 1e-300),
                    "denominator": denom,
                    "eq_transfer_lbmolps": math.nan,
                    "y_target": math.nan,
                    "y_eq": math.nan,
                    "K_eq_relax": math.nan,
                    "K_state_y_over_x": math.nan,
                    "K_state_over_K_thermo": math.nan,
                }
                if state_key in ("tray_L", "tray_V") and eq_transfer is not None:
                    # Positive eq_transfer adds vapor and removes liquid.
                    tr = float(eq_transfer[i, k])
                    row["eq_transfer_lbmolps"] = tr if state_key == "tray_V" else -tr
                if state_key == "tray_V":
                    if y_target is not None:
                        row["y_target"] = float(y_target[i, k])
                    if y_eq is not None:
                        row["y_eq"] = float(y_eq[i, k])
                    if k_eq is not None:
                        row["K_eq_relax"] = float(k_eq[i, k])
                    if k_state is not None:
                        row["K_state_y_over_x"] = float(k_state[i, k])
                    if k_ratio is not None:
                        row["K_state_over_K_thermo"] = float(k_ratio[i, k])
                yield row
    elif vals.ndim == 1:
        for idx in range(vals.size):
            inventory = float(vals[idx])
            rate = float(dr[idx])
            if state_key.startswith("tray_"):
                stage_1based = int(idx + 1)
                comp_1based = math.nan
                comp_name = ""
            elif state_key.startswith("top_"):
                stage_1based = 0
                comp_1based = int(idx + 1)
                comp_name = component_names[idx] if idx < len(component_names) else f"component_{idx + 1}"
            elif state_key.startswith("bottom_"):
                stage_1based = int(n_stages + 1)
                comp_1based = int(idx + 1)
                comp_name = component_names[idx] if idx < len(component_names) else f"component_{idx + 1}"
            else:
                stage_1based = math.nan
                comp_1based = math.nan
                comp_name = ""
            denom = abs(inventory) + floor
            yield {
                "state_key": state_key,
                "stage_1based": stage_1based,
                "component_1based": comp_1based,
                "component_name": comp_name,
                "inventory_lbmol_or_BTU": inventory,
                "rate_per_s": rate,
                "rate_lbmolph_or_BTUph": rate * 3600.0,
                "relative_rate_per_s": abs(rate) / max(denom, 1e-300),
                "denominator": denom,
                "eq_transfer_lbmolps": math.nan,
                "y_target": math.nan,
                "y_eq": math.nan,
                "K_eq_relax": math.nan,
                "K_state_y_over_x": math.nan,
                "K_state_over_K_thermo": math.nan,
            }


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank state-vector rates at t=0 for a column workbook.")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["stub", "relative-volatility", "simple-rv", "constant-alpha", "clapeyron", "table", "table-pool", "dwsim"],
        default="table-pool",
    )
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--clapeyron-model", dest="clapeyron_model", default="PR")
    ap.add_argument("--dwsim-property-package", dest="dwsim_property_package", default="pr")
    ap.add_argument(
        "--runtime-mode",
        dest="runtime_mode",
        choices=["legacy", "parity", "calibration", "hydraulic"],
        default="legacy",
        help="Runner runtime-mode preset to audit against.",
    )
    ap.add_argument("--scenario", dest="scenario", default="default")
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-energy", dest="include_energy", action="store_false")
    ap.set_defaults(include_temperature=True, include_energy=False)
    ap.add_argument(
        "--disable-boundary-states",
        dest="include_boundary_states",
        action="store_false",
        help="Audit source-topology cases without extra top/bottom boundary states.",
    )
    ap.set_defaults(include_boundary_states=True)
    ap.add_argument(
        "--disable-vapor-states",
        dest="include_vapor_states",
        action="store_false",
        help="Audit source-topology cases without dynamic tray vapor states.",
    )
    ap.set_defaults(include_vapor_states=True)
    ap.add_argument("--use-excel-vapor-holdup", dest="use_excel_vapor_holdup", action="store_true")
    ap.add_argument("--denom-floor-lbmol", dest="denom_floor_lbmol", type=float, default=1.0)
    ap.add_argument("--top", dest="top_n", type=int, default=40)
    ap.add_argument("--output-csv", dest="output_csv", default=None)
    ap.add_argument("--output-summary", dest="output_summary", default=None)
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    excel_path = _resolve_path(project_root, str(args.excel_path))
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo_mode).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(project_root, str(args.thermo_table_path))
        if not thermo_table_path.exists():
            raise FileNotFoundError(f"Thermo table file not found: {thermo_table_path}")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=bool(args.include_boundary_states),
        include_bottom=bool(args.include_boundary_states),
        include_vapor=bool(args.include_vapor_states),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
    )

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        clapeyron_model=str(args.clapeyron_model),
        dwsim_property_package=str(args.dwsim_property_package),
        runtime_mode=str(args.runtime_mode),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        write_logs=False,
    )

    base_inputs, _provider = build_inputs_for_runner(case, col, cfg)
    inputs = _scenario_inputs(base_inputs, str(args.scenario))
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

    component_names = [str(v) for v in getattr(col, "components_excel", [])]
    if not component_names:
        component_names = [f"component_{i + 1}" for i in range(int(col.n_components))]

    rows: List[Dict[str, Any]] = []
    for key in ("tray_L", "tray_V", "top_L", "top_V", "bottom_L", "bottom_V", "tray_EL_BTU", "tray_EV_BTU", "tray_T_f"):
        if key not in u or key not in du:
            continue
        rows.extend(
            _iter_block_rows(
                state_key=key,
                values=np.asarray(u[key], dtype=float),
                rates=np.asarray(du[key], dtype=float),
                denom_floor_lbmol=float(args.denom_floor_lbmol),
                component_names=component_names,
                n_stages=int(col.n_stages),
                diag=diag,
            )
        )

    rows.sort(key=lambda r: abs(float(r.get("relative_rate_per_s", 0.0))), reverse=True)
    top_n = max(int(args.top_n), 1)
    out_rows = rows[:top_n]

    out_csv = _resolve_path(project_root, str(args.output_csv)) if args.output_csv else (
        project_root / "logs" / f"state_rate_audit_{_timestamp_tag()}.csv"
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "state_key",
        "stage_1based",
        "component_1based",
        "component_name",
        "inventory_lbmol_or_BTU",
        "rate_per_s",
        "rate_lbmolph_or_BTUph",
        "relative_rate_per_s",
        "denominator",
        "eq_transfer_lbmolps",
        "y_target",
        "y_eq",
        "K_eq_relax",
        "K_state_y_over_x",
        "K_state_over_K_thermo",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rank, row in enumerate(out_rows, start=1):
            writer.writerow({"rank": rank, **{k: row.get(k, "") for k in fieldnames if k != "rank"}})

    summary_lines: List[str] = []
    summary_lines.append(f"excel: {excel_path}")
    summary_lines.append(f"thermo: {args.thermo_mode}")
    summary_lines.append(f"scenario: {args.scenario}")
    summary_lines.append(f"pressure_model: {getattr(inputs, 'pressure_model', '')}")
    summary_lines.append(f"vapor_flow_model: {getattr(inputs, 'vapor_flow_model', '')}")
    summary_lines.append(f"equilibrium_relaxation: {bool(getattr(inputs, 'equilibrium_relaxation', False))}")
    summary_lines.append(f"equilibrium_mode_comp_only: {_diag_scalar(diag, 'eq_relaxation_mode_comp_only')}")
    summary_lines.append(f"eq_relax_thermo_override_active: {_diag_scalar(diag, 'eq_relax_thermo_override_active')}")
    summary_lines.append(f"denom_floor_lbmol: {float(args.denom_floor_lbmol):.6g}")
    if out_rows:
        b = out_rows[0]
        summary_lines.append(
            "worst_state: "
            f"{b['state_key']} stage={b['stage_1based']} comp={b['component_1based']} "
            f"{b['component_name']} rel={float(b['relative_rate_per_s']):.8g} 1/s "
            f"rate={float(b['rate_per_s']):.8g}/s inventory={float(b['inventory_lbmol_or_BTU']):.8g}"
        )
    summary_lines.append(f"output_csv: {out_csv}")

    out_summary = _resolve_path(project_root, str(args.output_summary)) if args.output_summary else None
    if out_summary is not None:
        out_summary.parent.mkdir(parents=True, exist_ok=True)
        out_summary.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("\n".join(summary_lines))
    print("\nTop rates:")
    for rank, row in enumerate(out_rows[: min(top_n, 12)], start=1):
        print(
            f"{rank:2d}. {row['state_key']} stage={row['stage_1based']} "
            f"comp={row['component_1based']} {row['component_name']} "
            f"rel={float(row['relative_rate_per_s']):.8g}/s "
            f"rate={float(row['rate_per_s']):.8g}/s "
            f"inv={float(row['inventory_lbmol_or_BTU']):.8g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
