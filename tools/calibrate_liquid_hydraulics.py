#!/usr/bin/env python
"""
Calibrate tray liquid hydraulics to match the ChemSep/Excel liquid-flow profile.

Purpose
-------
Fit section-level multipliers on Francis-weir hydraulic parameters so predicted
internal tray liquid downflow (stages 2..N-1) is closer to the input
steady-state liquid profile from Excel.

This is a constrained calibration utility, not a generic optimizer.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Allow "python tools/..." usage without external PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, build_inputs_for_runner  # noqa: E402
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402


FRANCIS_C = 3.33
SEC_PER_HOUR = 3600.0
INCHES_PER_FOOT = 12.0


@dataclass(frozen=True)
class ParamSpec:
    kind: str  # "wh", "wl", "aa"
    sec_idx: int
    lo: float
    hi: float


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_path(project_root: Path, raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def _fit_mode_flags(mode: str) -> Tuple[bool, bool, bool, bool]:
    m = str(mode).strip().lower()
    if m == "weir-height":
        return True, False, False, False
    if m == "weir-length":
        return False, True, False, False
    if m == "active-area":
        return False, False, True, False
    if m == "c-multiplier":
        return False, False, False, True
    if m == "c-multiplier+weir-height":
        return True, False, False, True
    if m == "c-multiplier+weir-length":
        return False, True, False, True
    if m == "weir-height+weir-length":
        return True, True, False, False
    if m == "weir-height+active-area":
        return True, False, True, False
    if m == "all":
        return True, True, True, True
    raise ValueError(f"Unknown fit mode: {mode}")


def _section_index_by_stage(col: Any) -> np.ndarray:
    geom = getattr(col, "geometry", None)
    if geom is None:
        raise RuntimeError("Column has no geometry; hydraulic calibration requires Geometry Sections.")
    sections = list(getattr(geom, "sections", []) or [])
    n = int(col.n_stages)
    out = np.full(n, -1, dtype=int)
    for s_idx, sec in enumerate(sections):
        i0 = max(int(sec.start_stage_1based) - 1, 0)
        i1 = min(int(sec.end_stage_1based), n)
        out[i0:i1] = int(s_idx)
    if np.any(out < 0):
        # Assign any uncovered stages to nearest section by distance to section center.
        centers = np.array(
            [
                0.5 * (float(sec.start_stage_1based) + float(sec.end_stage_1based))
                for sec in sections
            ],
            dtype=float,
        )
        for i in np.where(out < 0)[0]:
            st = float(i + 1)
            out[i] = int(np.argmin(np.abs(centers - st)))
    return out


def _compute_rho_profile_lbmol_ft3(
    *,
    col: Any,
    provider: Any,
    rho_default: float,
) -> np.ndarray:
    n = int(col.n_stages)
    rho = np.full(n, np.nan, dtype=float)
    has_density = bool(provider is not None and hasattr(provider, "liquid_density_lbmol_ft3"))
    if has_density:
        for i in range(n):
            try:
                rho_i = float(
                    provider.liquid_density_lbmol_ft3(
                        float(col.T_f[i]),
                        float(col.P_psia[i]),
                        np.asarray(col.x0[i, :], dtype=float).reshape((col.n_components,)),
                    )
                )
                if np.isfinite(rho_i) and rho_i > 0.0:
                    rho[i] = rho_i
            except Exception:
                pass
    finite = np.isfinite(rho) & (rho > 0.0)
    if not np.any(finite):
        rho[:] = float(rho_default)
        return rho
    median_rho = float(np.median(rho[finite]))
    fill_val = median_rho if np.isfinite(median_rho) and median_rho > 0.0 else float(rho_default)
    rho[~finite] = fill_val
    return rho


def _predict_liquid_out_lbmolph(
    *,
    ML_lbmol: np.ndarray,
    rho_lbmol_ft3: np.ndarray,
    active_area_ft2: np.ndarray,
    weir_h_in: np.ndarray,
    weir_L_ft: np.ndarray,
    section_by_stage: np.ndarray,
    wh_scale: np.ndarray,
    wl_scale: np.ndarray,
    aa_scale: np.ndarray,
    c_base: np.ndarray,
    cm_scale: np.ndarray,
    fit_stage_mask: np.ndarray,
    eps_h_ft: float = 1e-6,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(ML_lbmol)
    L_pred = np.full(n, np.nan, dtype=float)
    h_total = np.full(n, np.nan, dtype=float)
    h_ow = np.full(n, np.nan, dtype=float)

    for i in range(n):
        if not bool(fit_stage_mask[i]):
            continue
        sec = int(section_by_stage[i])
        rho = float(rho_lbmol_ft3[i])
        A = float(active_area_ft2[i]) * float(aa_scale[sec])
        h_w_ft = (float(weir_h_in[i]) * float(wh_scale[sec])) / INCHES_PER_FOOT
        Lw = float(weir_L_ft[i]) * float(wl_scale[sec])
        c_eff = float(c_base[i]) * float(cm_scale[sec])

        if (not np.isfinite(rho)) or rho <= 0.0:
            continue
        if (not np.isfinite(A)) or A <= 0.0:
            continue
        if (not np.isfinite(Lw)) or Lw <= 0.0:
            continue
        if (not np.isfinite(c_eff)) or c_eff <= 0.0:
            continue

        V_ft3 = float(ML_lbmol[i]) / rho
        h_t = V_ft3 / A
        hov = max(h_t - h_w_ft, eps_h_ft)

        Q_ft3_s = FRANCIS_C * c_eff * Lw * (hov ** 1.5)
        L_pred[i] = Q_ft3_s * rho * SEC_PER_HOUR
        h_total[i] = h_t
        h_ow[i] = hov
    return L_pred, h_total, h_ow


def _build_param_specs(
    *,
    n_sections: int,
    fit_wh: bool,
    fit_wl: bool,
    fit_aa: bool,
    fit_cm: bool,
    wh_bounds: Tuple[float, float],
    wl_bounds: Tuple[float, float],
    aa_bounds: Tuple[float, float],
    cm_bounds: Tuple[float, float],
) -> List[ParamSpec]:
    out: List[ParamSpec] = []
    for s in range(n_sections):
        if fit_wh:
            out.append(ParamSpec(kind="wh", sec_idx=s, lo=float(wh_bounds[0]), hi=float(wh_bounds[1])))
        if fit_wl:
            out.append(ParamSpec(kind="wl", sec_idx=s, lo=float(wl_bounds[0]), hi=float(wl_bounds[1])))
        if fit_aa:
            out.append(ParamSpec(kind="aa", sec_idx=s, lo=float(aa_bounds[0]), hi=float(aa_bounds[1])))
        if fit_cm:
            out.append(ParamSpec(kind="cm", sec_idx=s, lo=float(cm_bounds[0]), hi=float(cm_bounds[1])))
    return out


def _decode_scales(
    x: np.ndarray,
    param_specs: Sequence[ParamSpec],
    n_sections: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    wh = np.ones(n_sections, dtype=float)
    wl = np.ones(n_sections, dtype=float)
    aa = np.ones(n_sections, dtype=float)
    cm = np.ones(n_sections, dtype=float)
    for v, p in zip(np.asarray(x, dtype=float), param_specs):
        if p.kind == "wh":
            wh[p.sec_idx] = float(v)
        elif p.kind == "wl":
            wl[p.sec_idx] = float(v)
        elif p.kind == "aa":
            aa[p.sec_idx] = float(v)
        elif p.kind == "cm":
            cm[p.sec_idx] = float(v)
    return wh, wl, aa, cm


def _objective_factory(
    *,
    L_target_lbmolph: np.ndarray,
    ML_lbmol: np.ndarray,
    rho_lbmol_ft3: np.ndarray,
    active_area_ft2: np.ndarray,
    weir_h_in: np.ndarray,
    weir_L_ft: np.ndarray,
    c_base: np.ndarray,
    section_by_stage: np.ndarray,
    fit_stage_mask: np.ndarray,
    param_specs: Sequence[ParamSpec],
    n_sections: int,
    regularization: float,
) -> Any:
    reg = max(float(regularization), 0.0)
    idx = np.where(fit_stage_mask)[0]
    target = np.asarray(L_target_lbmolph, dtype=float)

    def _obj(x: np.ndarray) -> float:
        wh, wl, aa, cm = _decode_scales(x, param_specs, n_sections)
        L_pred, _ht, _how = _predict_liquid_out_lbmolph(
            ML_lbmol=ML_lbmol,
            rho_lbmol_ft3=rho_lbmol_ft3,
            active_area_ft2=active_area_ft2,
            weir_h_in=weir_h_in,
            weir_L_ft=weir_L_ft,
            c_base=c_base,
            section_by_stage=section_by_stage,
            wh_scale=wh,
            wl_scale=wl,
            aa_scale=aa,
            cm_scale=cm,
            fit_stage_mask=fit_stage_mask,
        )
        pred = L_pred[idx]
        tgt = target[idx]
        if pred.size == 0:
            return 1e30
        if np.any(~np.isfinite(pred)):
            return 1e30
        denom = np.maximum(np.abs(tgt), 1.0)
        rel = (pred - tgt) / denom
        j = float(np.mean(np.square(rel)))
        if reg > 0.0 and len(param_specs) > 0:
            j += reg * float(np.mean(np.square(np.asarray(x, dtype=float) - 1.0)))
        return j

    return _obj


def _coordinate_descent(
    *,
    x0: np.ndarray,
    param_specs: Sequence[ParamSpec],
    obj_fn: Any,
    max_iters: int,
    init_step: float,
    min_step: float,
    tol: float = 1e-12,
) -> Tuple[np.ndarray, float, Dict[str, float]]:
    x = np.asarray(x0, dtype=float).copy()
    step = float(init_step)
    step = max(step, 1e-6)
    best = float(obj_fn(x))
    eval_count = 1

    for _ in range(max(int(max_iters), 1)):
        improved_any = False
        for j, p in enumerate(param_specs):
            base = float(x[j])
            cands = np.array(
                [base - step, base - 0.5 * step, base, base + 0.5 * step, base + step],
                dtype=float,
            )
            cands = np.clip(cands, float(p.lo), float(p.hi))
            cands = np.unique(np.round(cands, 12))
            best_local_x = base
            best_local_obj = best
            for v in cands:
                xx = x.copy()
                xx[j] = float(v)
                jj = float(obj_fn(xx))
                eval_count += 1
                if jj < (best_local_obj - tol):
                    best_local_obj = jj
                    best_local_x = float(v)
            if abs(best_local_x - base) > 0.0:
                x[j] = best_local_x
                best = best_local_obj
                improved_any = True

        if not improved_any:
            step *= 0.5
            if step < float(min_step):
                break

    meta = {"eval_count": float(eval_count), "final_step": float(step)}
    return x, float(best), meta


def _safe_pct(err: np.ndarray, ref: np.ndarray) -> np.ndarray:
    den = np.maximum(np.abs(np.asarray(ref, dtype=float)), 1e-12)
    return 100.0 * (np.asarray(err, dtype=float) / den)


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate tray liquid hydraulics against Excel L profile.")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument("--thermo", dest="thermo_mode", choices=["stub", "table", "table-pool", "dwsim"], default="table-pool")
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=6)
    ap.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    ap.add_argument("--rho-default", dest="rho_default", type=float, default=1.0)
    ap.add_argument(
        "--fit-mode",
        dest="fit_mode",
        choices=[
            "weir-height",
            "weir-length",
            "active-area",
            "c-multiplier",
            "c-multiplier+weir-height",
            "c-multiplier+weir-length",
            "weir-height+weir-length",
            "weir-height+active-area",
            "all",
        ],
        default="weir-height+weir-length",
    )
    ap.add_argument("--stage-start", dest="stage_start_1based", type=int, default=2)
    ap.add_argument("--stage-end", dest="stage_end_1based", type=int, default=None)
    ap.add_argument("--max-iters", dest="max_iters", type=int, default=30)
    ap.add_argument("--init-step", dest="init_step", type=float, default=0.20)
    ap.add_argument("--min-step", dest="min_step", type=float, default=0.01)
    ap.add_argument("--regularization", dest="regularization", type=float, default=1e-3)
    ap.add_argument("--wh-min", dest="wh_min", type=float, default=0.40)
    ap.add_argument("--wh-max", dest="wh_max", type=float, default=1.80)
    ap.add_argument("--wl-min", dest="wl_min", type=float, default=0.40)
    ap.add_argument("--wl-max", dest="wl_max", type=float, default=1.80)
    ap.add_argument("--aa-min", dest="aa_min", type=float, default=0.60)
    ap.add_argument("--aa-max", dest="aa_max", type=float, default=1.40)
    ap.add_argument("--cm-min", dest="cm_min", type=float, default=0.70)
    ap.add_argument("--cm-max", dest="cm_max", type=float, default=1.30)
    ap.add_argument("--out-prefix", dest="out_prefix", default=None)
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    excel_path = _resolve_path(project_root, str(args.excel_path))
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo_mode).strip().lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(project_root, str(args.thermo_table_path))
        if not thermo_table_path.exists():
            raise FileNotFoundError(f"Thermo table not found: {thermo_table_path}")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    geom = getattr(col, "geometry", None)
    if geom is None:
        raise RuntimeError("No geometry found in case. Add Geometry Sections before hydraulic calibration.")

    n = int(col.n_stages)
    nsec = len(list(getattr(geom, "sections", []) or []))
    if nsec <= 0:
        raise RuntimeError("Geometry exists but has no sections; cannot calibrate section-level parameters.")

    fit_start = max(int(args.stage_start_1based), 2)
    fit_end = int(args.stage_end_1based) if args.stage_end_1based is not None else (n - 1)
    fit_end = min(max(fit_end, fit_start), n - 1)
    fit_mask = np.zeros(n, dtype=bool)
    fit_mask[(fit_start - 1):fit_end] = True

    section_by_stage = _section_index_by_stage(col)
    ML = np.asarray(col.M_L_lbmol, dtype=float).reshape((n,))
    L_target = np.asarray(col.L_lbmolph, dtype=float).reshape((n,))
    weir_h = np.asarray(geom.weir_height_in_per_stage, dtype=float).reshape((n,))
    weir_L = np.asarray(geom.weir_length_ft_per_stage, dtype=float).reshape((n,))
    active_area = np.asarray(geom.active_area_ft2_per_stage, dtype=float).reshape((n,))
    c_base = np.asarray(
        getattr(geom, "hydraulic_c_factor_per_stage", np.ones(n, dtype=float)),
        dtype=float,
    ).reshape((n,))

    need_finite = fit_mask
    bad_msgs: List[str] = []
    if np.any(~np.isfinite(ML[need_finite])):
        bad = (np.where(~np.isfinite(ML[need_finite]))[0] + fit_start).tolist()
        bad_msgs.append(f"ML missing at fit stages: {bad}")
    if np.any(~np.isfinite(weir_h[need_finite])):
        bad = (np.where(~np.isfinite(weir_h[need_finite]))[0] + fit_start).tolist()
        bad_msgs.append(f"weir_height missing at fit stages: {bad}")
    if np.any(~np.isfinite(weir_L[need_finite])) or np.any(weir_L[need_finite] <= 0.0):
        bad = (np.where((~np.isfinite(weir_L[need_finite])) | (weir_L[need_finite] <= 0.0))[0] + fit_start).tolist()
        bad_msgs.append(f"weir_length invalid at fit stages: {bad}")
    if np.any(~np.isfinite(active_area[need_finite])) or np.any(active_area[need_finite] <= 0.0):
        bad = (np.where((~np.isfinite(active_area[need_finite])) | (active_area[need_finite] <= 0.0))[0] + fit_start).tolist()
        bad_msgs.append(f"active_area invalid at fit stages: {bad}")
    if np.any(~np.isfinite(c_base[need_finite])) or np.any(c_base[need_finite] <= 0.0):
        bad = (np.where((~np.isfinite(c_base[need_finite])) | (c_base[need_finite] <= 0.0))[0] + fit_start).tolist()
        bad_msgs.append(f"hydraulic/system factor invalid at fit stages: {bad}")
    if bad_msgs:
        raise RuntimeError("Invalid geometry/holdup for calibration:\n- " + "\n- ".join(bad_msgs))

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        thermo_pool_workers=int(args.thermo_pool_workers),
        thermo_pool_chunk_size=max(int(args.thermo_pool_chunk_size), 1),
        include_temperature=True,
        include_energy=False,
        write_logs=False,
    )
    _inputs, provider = build_inputs_for_runner(case, col, cfg)
    rho = _compute_rho_profile_lbmol_ft3(col=col, provider=provider, rho_default=float(args.rho_default))

    fit_wh, fit_wl, fit_aa, fit_cm = _fit_mode_flags(str(args.fit_mode))
    param_specs = _build_param_specs(
        n_sections=nsec,
        fit_wh=fit_wh,
        fit_wl=fit_wl,
        fit_aa=fit_aa,
        fit_cm=fit_cm,
        wh_bounds=(float(args.wh_min), float(args.wh_max)),
        wl_bounds=(float(args.wl_min), float(args.wl_max)),
        aa_bounds=(float(args.aa_min), float(args.aa_max)),
        cm_bounds=(float(args.cm_min), float(args.cm_max)),
    )
    x0 = np.ones(len(param_specs), dtype=float)

    obj_fn = _objective_factory(
        L_target_lbmolph=L_target,
        ML_lbmol=ML,
        rho_lbmol_ft3=rho,
        active_area_ft2=active_area,
        weir_h_in=weir_h,
        weir_L_ft=weir_L,
        c_base=c_base,
        section_by_stage=section_by_stage,
        fit_stage_mask=fit_mask,
        param_specs=param_specs,
        n_sections=nsec,
        regularization=float(args.regularization),
    )

    x_fit, j_fit, meta = _coordinate_descent(
        x0=x0,
        param_specs=param_specs,
        obj_fn=obj_fn,
        max_iters=int(args.max_iters),
        init_step=float(args.init_step),
        min_step=float(args.min_step),
    )
    j_base = float(obj_fn(x0))

    wh_base, wl_base, aa_base, cm_base = _decode_scales(x0, param_specs, nsec)
    wh_fit, wl_fit, aa_fit, cm_fit = _decode_scales(x_fit, param_specs, nsec)

    L_pred_base, h_total_base, h_ow_base = _predict_liquid_out_lbmolph(
        ML_lbmol=ML,
        rho_lbmol_ft3=rho,
        active_area_ft2=active_area,
        weir_h_in=weir_h,
        weir_L_ft=weir_L,
        c_base=c_base,
        section_by_stage=section_by_stage,
        wh_scale=wh_base,
        wl_scale=wl_base,
        aa_scale=aa_base,
        cm_scale=cm_base,
        fit_stage_mask=fit_mask,
    )
    L_pred_fit, h_total_fit, h_ow_fit = _predict_liquid_out_lbmolph(
        ML_lbmol=ML,
        rho_lbmol_ft3=rho,
        active_area_ft2=active_area,
        weir_h_in=weir_h,
        weir_L_ft=weir_L,
        c_base=c_base,
        section_by_stage=section_by_stage,
        wh_scale=wh_fit,
        wl_scale=wl_fit,
        aa_scale=aa_fit,
        cm_scale=cm_fit,
        fit_stage_mask=fit_mask,
    )

    idx = np.where(fit_mask)[0]
    e_base = L_pred_base[idx] - L_target[idx]
    e_fit = L_pred_fit[idx] - L_target[idx]
    pct_base = _safe_pct(e_base, L_target[idx])
    pct_fit = _safe_pct(e_fit, L_target[idx])

    def _mape(v: np.ndarray) -> float:
        vv = np.asarray(v, dtype=float)
        vv = vv[np.isfinite(vv)]
        return float(np.mean(np.abs(vv))) if vv.size > 0 else float("nan")

    mape_base = _mape(pct_base)
    mape_fit = _mape(pct_fit)
    max_abs_pct_base = float(np.nanmax(np.abs(pct_base))) if pct_base.size > 0 else float("nan")
    max_abs_pct_fit = float(np.nanmax(np.abs(pct_fit))) if pct_fit.size > 0 else float("nan")
    max_abs_err_base = float(np.nanmax(np.abs(e_base))) if e_base.size > 0 else float("nan")
    max_abs_err_fit = float(np.nanmax(np.abs(e_fit))) if e_fit.size > 0 else float("nan")

    tag = _timestamp_tag()
    prefix = str(args.out_prefix).strip() if args.out_prefix is not None else ""
    if prefix:
        prefix = prefix.rstrip("_") + "_"
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stage_csv = logs_dir / f"{prefix}liquid_hydraulic_calibration_stage_{tag}.csv"
    sec_csv = logs_dir / f"{prefix}liquid_hydraulic_calibration_sections_{tag}.csv"
    summary_txt = logs_dir / f"{prefix}liquid_hydraulic_calibration_summary_{tag}.txt"

    with stage_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "stage_1based",
                "fit_stage",
                "section_index",
                "L_target_lbmolph",
                "L_pred_base_lbmolph",
                "L_pred_fit_lbmolph",
                "err_base_lbmolph",
                "err_fit_lbmolph",
                "pct_err_base",
                "pct_err_fit",
                "rho_lbmol_ft3",
                "ML_lbmol",
                "c_base_factor",
                "c_fit_factor",
                "h_total_base_ft",
                "h_ow_base_ft",
                "h_total_fit_ft",
                "h_ow_fit_ft",
            ]
        )
        for i in range(n):
            err_b = float(L_pred_base[i] - L_target[i]) if np.isfinite(L_pred_base[i]) else np.nan
            err_f = float(L_pred_fit[i] - L_target[i]) if np.isfinite(L_pred_fit[i]) else np.nan
            pe_b = float(100.0 * err_b / max(abs(float(L_target[i])), 1e-12)) if np.isfinite(err_b) else np.nan
            pe_f = float(100.0 * err_f / max(abs(float(L_target[i])), 1e-12)) if np.isfinite(err_f) else np.nan
            w.writerow(
                [
                    i + 1,
                    int(bool(fit_mask[i])),
                    int(section_by_stage[i]),
                    float(L_target[i]),
                    float(L_pred_base[i]) if np.isfinite(L_pred_base[i]) else np.nan,
                    float(L_pred_fit[i]) if np.isfinite(L_pred_fit[i]) else np.nan,
                    err_b,
                    err_f,
                    pe_b,
                    pe_f,
                    float(rho[i]),
                    float(ML[i]),
                    float(c_base[i]),
                    float(c_base[i]) * float(cm_fit[int(section_by_stage[i])]),
                    float(h_total_base[i]) if np.isfinite(h_total_base[i]) else np.nan,
                    float(h_ow_base[i]) if np.isfinite(h_ow_base[i]) else np.nan,
                    float(h_total_fit[i]) if np.isfinite(h_total_fit[i]) else np.nan,
                    float(h_ow_fit[i]) if np.isfinite(h_ow_fit[i]) else np.nan,
                ]
            )

    with sec_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "section_index",
                "start_stage_1based",
                "end_stage_1based",
                "wh_scale",
                "wl_scale",
                "aa_scale",
                "cm_scale",
                "base_weir_height_in",
                "fit_weir_height_in",
                "base_weir_length_ft",
                "fit_weir_length_ft",
                "base_active_area_frac",
                "fit_active_area_frac",
                "base_system_factor",
                "fit_system_factor",
            ]
        )
        sections = list(getattr(geom, "sections", []) or [])
        aaf_stage = np.asarray(geom.active_area_frac_per_stage, dtype=float).reshape((n,))
        for s_idx, sec in enumerate(sections):
            i0 = max(int(sec.start_stage_1based) - 1, 0)
            i1 = min(int(sec.end_stage_1based), n)
            aaf_base = np.nan
            if sec.active_area_frac is not None and np.isfinite(float(sec.active_area_frac)):
                aaf_base = float(sec.active_area_frac)
            else:
                seg = aaf_stage[i0:i1]
                if seg.size > 0 and np.any(np.isfinite(seg)):
                    aaf_base = float(np.nanmedian(seg))
            aaf_fit = aaf_base * float(aa_fit[s_idx]) if np.isfinite(aaf_base) else np.nan

            wh_b = float(sec.weir_height_in) if sec.weir_height_in is not None else np.nan
            wl_b = float(sec.weir_length_ft) if sec.weir_length_ft is not None else np.nan
            wh_f = wh_b * float(wh_fit[s_idx]) if np.isfinite(wh_b) else np.nan
            wl_f = wl_b * float(wl_fit[s_idx]) if np.isfinite(wl_b) else np.nan
            c_b_raw = getattr(sec, "hydraulic_c_factor", np.nan)
            c_b = float(c_b_raw) if c_b_raw is not None else np.nan
            if not np.isfinite(c_b) or c_b <= 0.0:
                segc = c_base[i0:i1]
                if segc.size > 0 and np.any(np.isfinite(segc) & (segc > 0.0)):
                    c_b = float(np.nanmedian(segc[np.isfinite(segc) & (segc > 0.0)]))
            c_f = c_b * float(cm_fit[s_idx]) if np.isfinite(c_b) else np.nan

            w.writerow(
                [
                    s_idx,
                    int(sec.start_stage_1based),
                    int(sec.end_stage_1based),
                    float(wh_fit[s_idx]),
                    float(wl_fit[s_idx]),
                    float(aa_fit[s_idx]),
                    float(cm_fit[s_idx]),
                    wh_b,
                    wh_f,
                    wl_b,
                    wl_f,
                    aaf_base,
                    aaf_fit,
                    c_b,
                    c_f,
                ]
            )

    lines = [
        "Liquid Hydraulic Calibration Summary",
        f"timestamp: {tag}",
        f"excel: {excel_path}",
        f"thermo_mode: {args.thermo_mode}",
        f"fit_mode: {args.fit_mode}",
        f"fit_stages: {fit_start}..{fit_end} (internal stages only)",
        f"n_sections: {nsec}",
        f"n_params: {len(param_specs)}",
        f"objective_base: {j_base:.8e}",
        f"objective_fit: {j_fit:.8e}",
        f"objective_improvement_pct: {100.0 * (j_base - j_fit) / max(j_base, 1e-30):.3f}",
        f"MAPE_base_pct: {mape_base:.4f}",
        f"MAPE_fit_pct: {mape_fit:.4f}",
        f"max_abs_pct_err_base: {max_abs_pct_base:.4f}",
        f"max_abs_pct_err_fit: {max_abs_pct_fit:.4f}",
        f"max_abs_err_base_lbmolph: {max_abs_err_base:.4f}",
        f"max_abs_err_fit_lbmolph: {max_abs_err_fit:.4f}",
        f"eval_count: {int(meta.get('eval_count', 0.0))}",
        f"final_step: {float(meta.get('final_step', np.nan)):.6f}",
        "",
        f"stage_csv: {stage_csv}",
        f"section_csv: {sec_csv}",
    ]
    summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print("")
    print("Recommended Geometry Sections updates (apply in Excel):")
    print("section,start_stage,end_stage,weir_height_in,weir_length_ft,active_area_frac,system_factor")
    sections = list(getattr(geom, "sections", []) or [])
    aaf_stage = np.asarray(geom.active_area_frac_per_stage, dtype=float).reshape((n,))
    for s_idx, sec in enumerate(sections):
        i0 = max(int(sec.start_stage_1based) - 1, 0)
        i1 = min(int(sec.end_stage_1based), n)
        aaf_base = np.nan
        if sec.active_area_frac is not None and np.isfinite(float(sec.active_area_frac)):
            aaf_base = float(sec.active_area_frac)
        else:
            seg = aaf_stage[i0:i1]
            if seg.size > 0 and np.any(np.isfinite(seg)):
                aaf_base = float(np.nanmedian(seg))
        wh_b = float(sec.weir_height_in) if sec.weir_height_in is not None else np.nan
        wl_b = float(sec.weir_length_ft) if sec.weir_length_ft is not None else np.nan
        wh_f = wh_b * float(wh_fit[s_idx]) if np.isfinite(wh_b) else np.nan
        wl_f = wl_b * float(wl_fit[s_idx]) if np.isfinite(wl_b) else np.nan
        aaf_f = aaf_base * float(aa_fit[s_idx]) if np.isfinite(aaf_base) else np.nan
        c_b_raw = getattr(sec, "hydraulic_c_factor", np.nan)
        c_b = float(c_b_raw) if c_b_raw is not None else np.nan
        if not np.isfinite(c_b) or c_b <= 0.0:
            segc = c_base[i0:i1]
            if segc.size > 0 and np.any(np.isfinite(segc) & (segc > 0.0)):
                c_b = float(np.nanmedian(segc[np.isfinite(segc) & (segc > 0.0)]))
        c_f = c_b * float(cm_fit[s_idx]) if np.isfinite(c_b) else np.nan
        print(
            f"{s_idx},{int(sec.start_stage_1based)},{int(sec.end_stage_1based)},"
            f"{wh_f:.6g},{wl_f:.6g},{aaf_f:.6g},{c_f:.6g}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
