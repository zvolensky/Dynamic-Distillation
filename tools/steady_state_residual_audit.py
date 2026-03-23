#!/usr/bin/env python
"""
Steady-state residual audit for the dynamic column model.

This tool evaluates RHS residuals at initialized state (t=0) for a scenario
matrix and reports which modeling assumptions are most/least self-consistent.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
from dataclasses import dataclass, replace
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Allow direct "python tools/..." usage without requiring external PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import ColumnInputs, column_rhs
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.dynamic_run_scaffold_v1 import (
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_vapor_holdup_from_spec_pressure,
    build_inputs_for_runner,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    pressure_model: str
    vapor_flow_model: str
    flash_feed_at_stage_conditions: bool


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    pressure_model: str
    vapor_flow_model: str
    flash_feed_at_stage_conditions: bool
    worst_tray_stage_1based: int
    feed_stage_1based: Optional[int]
    feed_tray_inventory_rate_lbmolph: float
    max_abs_tray_inventory_rate_lbmolph: float
    rms_tray_inventory_rate_lbmolph: float
    top_inventory_rate_lbmolph: float
    bottom_inventory_rate_lbmolph: float
    total_inventory_rate_from_state_lbmolph: float
    total_inventory_rate_from_diag_lbmolph: float
    global_mass_closure_error_lbmolph: float
    max_abs_tray_component_rate_lbmolph: float
    max_abs_temperature_rate_F_per_s: float
    max_abs_energy_rate_BTU_per_s: float
    top_pressure_psia: float


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


def _extract_top_pressure_psia(diag: Dict[str, Any], n_stages: int) -> float:
    v = _diag_scalar(diag, "P_top_drum_psia")
    if np.isfinite(v) and v > 0.0:
        return float(v)
    for key in ("P_psia_hyd", "P_psia_diag"):
        if key not in diag:
            continue
        try:
            p = np.asarray(diag[key], dtype=float).reshape((n_stages,))
            vv = _as_float(p[0], default=math.nan)
            if np.isfinite(vv) and vv > 0.0:
                return float(vv)
        except Exception:
            continue
    return math.nan


def _feed_stage_1based(col: Any) -> Optional[int]:
    streams = getattr(col, "streams", None)
    if not isinstance(streams, dict):
        return None
    for name, spec in streams.items():
        nm = str(name).strip().lower()
        if "feed" not in nm:
            continue
        try:
            stage = getattr(spec, "stage_1based", None)
            if stage is not None:
                v = int(stage)
                if v >= 1:
                    return v
        except Exception:
            continue
    return None


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
    )
    return np.asarray(y, dtype=float)


def _scenario_matrix(base_inputs: ColumnInputs) -> List[ScenarioSpec]:
    p0 = str(getattr(base_inputs, "pressure_model", "spec")).strip().lower() or "spec"
    v0 = str(getattr(base_inputs, "vapor_flow_model", "profile")).strip().lower() or "profile"
    f0 = bool(getattr(base_inputs, "flash_feed_at_stage_conditions", True))
    candidates: List[ScenarioSpec] = [
        ScenarioSpec(
            name="default_from_case",
            pressure_model=p0,
            vapor_flow_model=v0,
            flash_feed_at_stage_conditions=f0,
        ),
        ScenarioSpec(
            name="spec_profile_no_feed_flash",
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=False,
        ),
        ScenarioSpec(
            name="spec_profile_with_feed_flash",
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=True,
        ),
        ScenarioSpec(
            name="hydraulic_energy_no_feed_flash",
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=False,
        ),
        ScenarioSpec(
            name="hydraulic_energy_with_feed_flash",
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=True,
        ),
    ]
    out: List[ScenarioSpec] = []
    seen: set[Tuple[str, str, bool]] = set()
    for c in candidates:
        key = (c.pressure_model, c.vapor_flow_model, c.flash_feed_at_stage_conditions)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _evaluate_scenario(
    *,
    col: Any,
    layout: StateVectorLayout,
    base_inputs: ColumnInputs,
    scenario: ScenarioSpec,
    include_temperature: bool,
    use_excel_vapor_holdup: bool,
    feed_stage_1based: Optional[int],
) -> ScenarioResult:
    inputs = replace(
        base_inputs,
        pressure_model=str(scenario.pressure_model),
        vapor_flow_model=str(scenario.vapor_flow_model),
        flash_feed_at_stage_conditions=bool(scenario.flash_feed_at_stage_conditions),
    )
    y0 = _build_initial_state(
        col=col,
        layout=layout,
        inputs=inputs,
        include_temperature=bool(include_temperature),
        use_excel_vapor_holdup=bool(use_excel_vapor_holdup),
    )

    dydt, diag = column_rhs(0.0, y0, col, layout, inputs)
    du = layout.unpack(np.asarray(dydt, dtype=float))
    tray_L = np.asarray(du["tray_L"], dtype=float).reshape((col.n_stages, col.n_components))
    tray_V = np.asarray(du["tray_V"], dtype=float).reshape((col.n_stages, col.n_components))
    tray_rate = np.sum(tray_L, axis=1) + np.sum(tray_V, axis=1)  # lbmol/s
    tray_rate_ph = tray_rate * 3600.0
    worst_idx = int(np.argmax(np.abs(tray_rate_ph)))
    max_abs_tray = float(np.max(np.abs(tray_rate_ph)))
    rms_tray = float(np.sqrt(np.mean(np.square(tray_rate_ph))))

    top_rate = 0.0
    if "top_L" in du:
        top_rate += float(np.sum(np.asarray(du["top_L"], dtype=float)))
    if "top_V" in du:
        top_rate += float(np.sum(np.asarray(du["top_V"], dtype=float)))
    top_rate_ph = float(top_rate * 3600.0)

    bot_rate = 0.0
    if "bottom_L" in du:
        bot_rate += float(np.sum(np.asarray(du["bottom_L"], dtype=float)))
    if "bottom_V" in du:
        bot_rate += float(np.sum(np.asarray(du["bottom_V"], dtype=float)))
    bot_rate_ph = float(bot_rate * 3600.0)

    total_state_rate = float(np.sum(tray_rate_ph) + top_rate_ph + bot_rate_ph)

    max_abs_comp = float(
        np.max(
            np.abs(
                np.concatenate(
                    [
                        tray_L.reshape((-1,)),
                        tray_V.reshape((-1,)),
                        (np.asarray(du["top_L"], dtype=float).reshape((-1,)) if "top_L" in du else np.zeros(0)),
                        (np.asarray(du["top_V"], dtype=float).reshape((-1,)) if "top_V" in du else np.zeros(0)),
                        (np.asarray(du["bottom_L"], dtype=float).reshape((-1,)) if "bottom_L" in du else np.zeros(0)),
                        (np.asarray(du["bottom_V"], dtype=float).reshape((-1,)) if "bottom_V" in du else np.zeros(0)),
                    ]
                )
            )
        )
        * 3600.0
    )

    dT_max = math.nan
    if "tray_T_f" in du:
        dT_max = float(np.max(np.abs(np.asarray(du["tray_T_f"], dtype=float).reshape((-1,)))))
    dE_max = math.nan
    if "tray_EL_BTU" in du:
        dE_max = float(np.max(np.abs(np.asarray(du["tray_EL_BTU"], dtype=float).reshape((-1,)))))
    if "tray_EV_BTU" in du:
        dE2 = float(np.max(np.abs(np.asarray(du["tray_EV_BTU"], dtype=float).reshape((-1,)))))
        dE_max = dE2 if not np.isfinite(dE_max) else max(dE_max, dE2)

    feed_rate = math.nan
    if feed_stage_1based is not None:
        i = int(feed_stage_1based) - 1
        if 0 <= i < tray_rate_ph.size:
            feed_rate = float(tray_rate_ph[i])

    return ScenarioResult(
        scenario=str(scenario.name),
        pressure_model=str(scenario.pressure_model),
        vapor_flow_model=str(scenario.vapor_flow_model),
        flash_feed_at_stage_conditions=bool(scenario.flash_feed_at_stage_conditions),
        worst_tray_stage_1based=int(worst_idx + 1),
        feed_stage_1based=(None if feed_stage_1based is None else int(feed_stage_1based)),
        feed_tray_inventory_rate_lbmolph=float(feed_rate),
        max_abs_tray_inventory_rate_lbmolph=float(max_abs_tray),
        rms_tray_inventory_rate_lbmolph=float(rms_tray),
        top_inventory_rate_lbmolph=float(top_rate_ph),
        bottom_inventory_rate_lbmolph=float(bot_rate_ph),
        total_inventory_rate_from_state_lbmolph=float(total_state_rate),
        total_inventory_rate_from_diag_lbmolph=_diag_scalar(diag, "dM_total_dt_lbmolph"),
        global_mass_closure_error_lbmolph=_diag_scalar(diag, "global_mass_closure_error_lbmolph"),
        max_abs_tray_component_rate_lbmolph=float(max_abs_comp),
        max_abs_temperature_rate_F_per_s=float(dT_max),
        max_abs_energy_rate_BTU_per_s=float(dE_max),
        top_pressure_psia=_extract_top_pressure_psia(diag, col.n_stages),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Steady-state residual audit at initialized conditions.")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument("--thermo", dest="thermo_mode", choices=["stub", "table", "table-pool", "dwsim"], default="table")
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=None)
    ap.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    ap.add_argument(
        "--runtime-mode",
        dest="runtime_mode",
        choices=["legacy", "parity", "calibration", "hydraulic", "huang", "huang-energy"],
        default="legacy",
        help="Runner runtime-mode preset to audit against.",
    )
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-energy", dest="include_energy", action="store_false")
    ap.set_defaults(include_temperature=True, include_energy=True)
    ap.add_argument("--single-scenario", dest="single_scenario", default=None)
    ap.add_argument("--use-excel-vapor-holdup", dest="use_excel_vapor_holdup", action="store_true")
    ap.add_argument("--output-csv", dest="output_csv", default=None)
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
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
    )

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=max(int(args.thermo_pool_chunk_size), 1),
        runtime_mode=str(args.runtime_mode),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        write_logs=False,
    )

    base_inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        scenarios = _scenario_matrix(base_inputs)
        if args.single_scenario:
            key = str(args.single_scenario).strip().lower()
            scenarios = [s for s in scenarios if s.name.strip().lower() == key]
            if not scenarios:
                raise ValueError(
                    f"Unknown scenario '{args.single_scenario}'. "
                    "Use one of: " + ", ".join(s.name for s in _scenario_matrix(base_inputs))
                )

        feed_stage = _feed_stage_1based(col)
        results: List[ScenarioResult] = []
        for s in scenarios:
            res = _evaluate_scenario(
                col=col,
                layout=layout,
                base_inputs=base_inputs,
                scenario=s,
                include_temperature=bool(args.include_temperature),
                use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
                feed_stage_1based=feed_stage,
            )
            results.append(res)

        results_sorted = sorted(results, key=lambda r: float(r.max_abs_tray_inventory_rate_lbmolph))

        if args.output_csv:
            out_csv = _resolve_path(project_root, str(args.output_csv))
        else:
            out_csv = project_root / "logs" / f"steady_state_residual_audit_{_timestamp_tag()}.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)

        fields = [f.name for f in ScenarioResult.__dataclass_fields__.values()]
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in results:
                w.writerow({k: getattr(r, k) for k in fields})

        print("Steady-state residual audit")
        print(f"Excel case: {excel_path}")
        print(f"Thermo mode: {str(args.thermo_mode).lower()}")
        print(f"Runtime mode: {str(args.runtime_mode).lower()}")
        print(
            f"State basis: include_temperature={bool(args.include_temperature)} "
            f"include_energy={bool(args.include_energy)}"
        )
        if feed_stage is not None:
            print(f"Feed stage (1-based): {int(feed_stage)}")
        print("")
        print("Scenario ranking (lower max |tray inventory rate| is better):")
        for r in results_sorted:
            print(
                f"  {r.scenario}: "
                f"max|dM_tray|={float(r.max_abs_tray_inventory_rate_lbmolph):.6g} lbmol/h, "
                f"rms={float(r.rms_tray_inventory_rate_lbmolph):.6g}, "
                f"worst_stage={int(r.worst_tray_stage_1based)}, "
                f"topP={float(r.top_pressure_psia):.6g} psia"
            )
        print("")
        best = results_sorted[0]
        print("Best scenario (by tray inventory residual):")
        print(
            f"  {best.scenario}  "
            f"[pressure_model={best.pressure_model}, "
            f"vapor_flow_model={best.vapor_flow_model}, "
            f"flash_feed_at_stage_conditions={best.flash_feed_at_stage_conditions}]"
        )
        print("")
        print(f"Wrote: {out_csv}")
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
