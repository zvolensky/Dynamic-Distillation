#!/usr/bin/env python
"""
Project a native checkpoint's internal liquid holdups toward material closure.

The projection keeps liquid compositions fixed and changes only internal tray
liquid totals so Francis-weir hydraulics match the liquid-flow profile implied
by the current vapor-flow profile and feed. Top and bottom stages are left
unchanged because their balances include explicit boundary equipment.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import _feed_component_rates_lbmolps  # noqa: E402
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    build_inputs_for_runner,
    read_native_checkpoint,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.stage_hydraulics_francis_v1 import FRANCIS_C, INCHES_PER_FOOT, SEC_PER_HOUR  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _resolve_path(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _layout_from_doc(doc: Dict[str, Any]) -> StateVectorLayout:
    return StateVectorLayout(
        n_stages=int(doc["n_stages"]),
        n_components=int(doc["n_components"]),
        include_top=bool(doc.get("include_top", True)),
        include_bottom=bool(doc.get("include_bottom", True)),
        include_vapor=bool(doc.get("include_vapor", True)),
        include_temperature=bool(doc.get("include_temperature", False)),
        include_energy=bool(doc.get("include_energy", False)),
    )


def _finite_vec(arr: Any, n: int, fill: float = np.nan) -> np.ndarray:
    try:
        out = np.asarray(arr, dtype=float).reshape((n,))
    except Exception:
        return np.full(n, float(fill), dtype=float)
    return out


def _target_internal_liquid_flows(
    *,
    current_l_out_lbmolph: np.ndarray,
    v_out_lbmolph: np.ndarray,
    feed_total_lbmolph: np.ndarray,
) -> np.ndarray:
    n = int(current_l_out_lbmolph.size)
    target = np.asarray(current_l_out_lbmolph, dtype=float).reshape((n,)).copy()
    if n < 3:
        return target
    for i in range(1, n - 1):
        v_in = float(v_out_lbmolph[i + 1]) if i + 1 < n else float(v_out_lbmolph[i])
        target[i] = (
            float(target[i - 1])
            + v_in
            - float(v_out_lbmolph[i])
            + float(feed_total_lbmolph[i])
        )
    return np.maximum(target, 0.0)


def _invert_francis_holdup(
    *,
    l_target_lbmolph: np.ndarray,
    rho_lbmol_ft3: np.ndarray,
    active_area_ft2: np.ndarray,
    holdup_area_ft2: np.ndarray,
    weir_height_in: np.ndarray,
    weir_length_ft: np.ndarray,
    c_factor: np.ndarray,
    old_ml_lbmol: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    n = int(old_ml_lbmol.size)
    ml_new = np.asarray(old_ml_lbmol, dtype=float).reshape((n,)).copy()
    h_ow = np.full(n, np.nan, dtype=float)
    for i in range(1, n - 1):
        rho = float(rho_lbmol_ft3[i])
        area = float(holdup_area_ft2[i])
        weir_h_ft = float(weir_height_in[i]) / INCHES_PER_FOOT
        weir_l = float(weir_length_ft[i])
        c = float(c_factor[i])
        target = max(float(l_target_lbmolph[i]), 0.0)
        if (
            not np.isfinite(rho)
            or rho <= 0.0
            or not np.isfinite(area)
            or area <= 0.0
            or not np.isfinite(weir_l)
            or weir_l <= 0.0
            or not np.isfinite(c)
            or c <= 0.0
        ):
            continue
        den = FRANCIS_C * c * weir_l * rho * SEC_PER_HOUR
        hover = 0.0 if target <= 0.0 else float((target / den) ** (2.0 / 3.0))
        h_ow[i] = hover
        ml_new[i] = rho * area * (weir_h_ft + hover)
    return ml_new, h_ow


def main() -> int:
    ap = argparse.ArgumentParser(description="Project checkpoint liquid holdups to internal material closure.")
    ap.add_argument("--excel", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--thermo", choices=["stub", "table", "table-pool", "dwsim", "clapeyron"], default="table")
    ap.add_argument("--thermo-table", default="cache/thermo_table.json")
    ap.add_argument("--no-flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_false")
    ap.add_argument("--flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_true")
    ap.set_defaults(flash_feed_at_stage_conditions=False)
    args = ap.parse_args()

    excel_path = _resolve_path(args.excel)
    checkpoint_path = _resolve_path(args.checkpoint)
    output_path = _resolve_path(args.output)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Native checkpoint file not found: {checkpoint_path}")

    checkpoint = read_native_checkpoint(checkpoint_path)
    metadata = dict(checkpoint.get("metadata") or {})
    arrays = dict(checkpoint.get("arrays") or {})
    layout_doc = metadata.get("layout") if isinstance(metadata.get("layout"), dict) else {}
    layout = _layout_from_doc(layout_doc)
    y = np.asarray(arrays["final_state"], dtype=float).reshape((-1,)).copy()
    u = layout.unpack(y)
    if "tray_L" not in u:
        raise ValueError("Checkpoint layout does not include tray_L.")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    n = int(col.n_stages)
    nc = int(col.n_components)
    if n != int(layout.n_stages) or nc != int(layout.n_components):
        raise ValueError("Checkpoint layout does not match Excel case dimensions.")
    geom = getattr(col, "geometry", None)
    if geom is None:
        raise ValueError("Column case has no geometry; cannot invert Francis hydraulics.")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(args.thermo_table)
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode="hydraulic",
        thermo_mode=str(args.thermo),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        include_temperature=bool(layout.include_temperature),
        include_energy=bool(layout.include_energy),
        flash_feed_at_stage_conditions=bool(args.flash_feed_at_stage_conditions),
        write_logs=False,
    )
    inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        tray_l = np.asarray(u["tray_L"], dtype=float).reshape((n, nc)).copy()
        old_ml = np.sum(tray_l, axis=1)
        l_out_current = _finite_vec(arrays.get("diag__L_out_lbmolph"), n, fill=np.nan)
        v_out = _finite_vec(arrays.get("diag__V_out_lbmolph"), n, fill=np.nan)
        rho = _finite_vec(arrays.get("diag__rhoL_tray_lbmol_ft3"), n, fill=np.nan)
        if not np.all(np.isfinite(l_out_current)) or not np.all(np.isfinite(v_out)):
            raise ValueError("Checkpoint is missing finite diag__L_out_lbmolph or diag__V_out_lbmolph arrays.")
        if not np.all(np.isfinite(rho)) or np.nanmin(rho) <= 0.0:
            rho = np.full(n, 1.0, dtype=float)

        p_feed = _finite_vec(arrays.get("diag__P_psia_hyd"), n, fill=np.nan)
        if not np.all(np.isfinite(p_feed)):
            p_feed = np.asarray(getattr(col, "P_psia", np.full(n, np.nan)), dtype=float).reshape((n,))
        feed_stage0, fk_l, fk_v = _feed_component_rates_lbmolps(
            col=col,
            Nc=nc,
            thermo_provider=provider,
            P_tray_psia=p_feed,
            flash_feed_at_stage_conditions=bool(args.flash_feed_at_stage_conditions),
        )
        feed_total = np.zeros(n, dtype=float)
        if feed_stage0 is not None and 0 <= int(feed_stage0) < n:
            feed_total[int(feed_stage0)] = float((np.sum(fk_l) + np.sum(fk_v)) * SEC_PER_HOUR)

        target_l = _target_internal_liquid_flows(
            current_l_out_lbmolph=l_out_current,
            v_out_lbmolph=v_out,
            feed_total_lbmolph=feed_total,
        )

        active_area = np.asarray(geom.active_area_ft2_per_stage, dtype=float).reshape((n,))
        holdup_area_raw = getattr(geom, "holdup_area_ft2_per_stage", None)
        holdup_area = active_area if holdup_area_raw is None else np.asarray(holdup_area_raw, dtype=float).reshape((n,))
        weir_h = np.asarray(geom.weir_height_in_per_stage, dtype=float).reshape((n,))
        weir_l = np.asarray(geom.weir_length_ft_per_stage, dtype=float).reshape((n,))
        c_factor_raw = getattr(geom, "hydraulic_c_factor_per_stage", None)
        c_factor = np.ones(n, dtype=float) if c_factor_raw is None else np.asarray(c_factor_raw, dtype=float).reshape((n,))
        new_ml, h_ow = _invert_francis_holdup(
            l_target_lbmolph=target_l,
            rho_lbmol_ft3=rho,
            active_area_ft2=active_area,
            holdup_area_ft2=holdup_area,
            weir_height_in=weir_h,
            weir_length_ft=weir_l,
            c_factor=c_factor,
            old_ml_lbmol=old_ml,
        )

        new_tray_l = tray_l.copy()
        for i in range(1, n - 1):
            total = float(old_ml[i])
            if total > 0.0 and np.isfinite(new_ml[i]) and new_ml[i] > 0.0:
                new_tray_l[i, :] = tray_l[i, :] * (float(new_ml[i]) / total)
        y[layout.slices()["tray_L"]] = new_tray_l.reshape((-1,))

        arrays["final_state"] = y.copy()
        metadata["liquid_holdup_closure_projection"] = {
            "schema": "dynamic_distillation.liquid_holdup_closure_projection.v1",
            "source_checkpoint": str(checkpoint_path),
            "created_at": _timestamp_tag(),
            "method": "internal_francis_inverse_from_vapor_profile",
            "top_bottom_unchanged": True,
            "flash_feed_at_stage_conditions": bool(args.flash_feed_at_stage_conditions),
            "max_abs_internal_L_target_delta_lbmolph": float(np.nanmax(np.abs(target_l[1:-1] - l_out_current[1:-1]))),
            "max_abs_internal_ML_delta_lbmol": float(np.nanmax(np.abs(new_ml[1:-1] - old_ml[1:-1]))),
            "feed_stage_1based": None if feed_stage0 is None else int(feed_stage0 + 1),
            "feed_total_lbmolph": float(np.sum(feed_total)),
        }
        metadata["array_keys"] = sorted(arrays.keys())
        arrays["metadata_json"] = np.asarray(json.dumps(metadata, indent=2, sort_keys=True, default=_json_default))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(output_path, **arrays)

        print("Projected checkpoint liquid holdups")
        print(f"Input: {checkpoint_path}")
        print(f"Output: {output_path}")
        print(f"Feed stage: {'' if feed_stage0 is None else int(feed_stage0 + 1)}")
        print(f"Feed total lbmol/h: {float(np.sum(feed_total)):.6g}")
        print(f"Max |internal L target delta| lbmol/h: {float(np.nanmax(np.abs(target_l[1:-1] - l_out_current[1:-1]))):.6g}")
        print(f"Max |internal ML delta| lbmol: {float(np.nanmax(np.abs(new_ml[1:-1] - old_ml[1:-1]))):.6g}")
        print("stage,ML_old,ML_new,L_current,L_target,h_ow_ft")
        for i in range(1, n - 1):
            print(
                f"{i + 1},{old_ml[i]:.8g},{new_ml[i]:.8g},"
                f"{l_out_current[i]:.8g},{target_l[i]:.8g},{h_ow[i]:.8g}"
            )
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
