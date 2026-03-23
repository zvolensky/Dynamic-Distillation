"""
dae_index_probe_v1.py

Lightweight structural diagnostics for the mini8 simultaneous UV pilot.

The goal is not to prove the formal DAE index symbolically. Instead, this
module quantifies which residual blocks are most weakly conditioned near the
current operating point so we can target regularization where it matters most.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.dae_pilot_v1 import finite_difference_jacobian, inf_norm
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.uv_flash_sandbox_simultaneous_v1 import (
    SimultaneousMini8Layout,
    default_algebraic_seed,
    evaluate_simultaneous_algebraic_state,
)
from dynamic_distillation.uv_flash_sandbox_v1 import (
    _build_provider,
    _pack_state,
    build_mini8_uv_prototype_spec,
)


@dataclass(frozen=True)
class _ProbeBlock:
    name: str
    row_slice: slice
    col_slice: slice


def _block_svd_metrics(block: np.ndarray, *, floor: float = 1.0e-12) -> Dict[str, float]:
    arr = np.asarray(block, dtype=float)
    if arr.size <= 0:
        return {
            "shape_rows": float(arr.shape[0] if arr.ndim >= 1 else 0),
            "shape_cols": float(arr.shape[1] if arr.ndim >= 2 else 0),
            "rank": 0.0,
            "sigma_max": 0.0,
            "sigma_min": 0.0,
            "cond": 1.0,
            "fro_norm": 0.0,
            "inf_norm": 0.0,
        }

    try:
        svals = np.linalg.svd(arr, compute_uv=False)
    except Exception:
        svals = np.asarray([], dtype=float)
    svals = np.asarray(svals, dtype=float).reshape((-1,))
    svals = svals[np.isfinite(svals)]
    sigma_max = float(np.max(svals)) if svals.size > 0 else 0.0
    sigma_min = float(np.min(svals)) if svals.size > 0 else 0.0
    rank = int(np.sum(svals > float(floor))) if svals.size > 0 else 0
    if sigma_max <= float(floor):
        cond = 1.0
    elif sigma_min <= float(floor):
        cond = float("inf")
    else:
        cond = float(sigma_max / sigma_min)
    return {
        "shape_rows": float(arr.shape[0]),
        "shape_cols": float(arr.shape[1]),
        "rank": float(rank),
        "sigma_max": float(sigma_max),
        "sigma_min": float(sigma_min),
        "cond": float(cond),
        "fro_norm": float(np.linalg.norm(arr, ord="fro")),
        "inf_norm": float(np.linalg.norm(arr, ord=np.inf)),
    }


def _build_probe_blocks(
    *,
    n_active: int,
    n_total_stages: int,
    include_vapor_regularization: bool = False,
) -> Dict[str, _ProbeBlock]:
    layout = SimultaneousMini8Layout(n_active=int(n_active), n_total_stages=int(n_total_stages))
    n_stage_rows = 3 * int(n_active)
    row_stage = slice(0, n_stage_rows)
    row_node = slice(row_stage.stop, row_stage.stop + 2)
    row_liquid = slice(row_node.stop, row_node.stop + int(n_total_stages))
    row_vapor = slice(row_liquid.stop, row_liquid.stop + int(n_total_stages))
    row_vreg = slice(row_vapor.stop, row_vapor.stop + int(n_total_stages))
    col_stage = slice(layout.stage_t_slice.start, layout.stage_beta_slice.stop)
    col_node = slice(layout.top_t_idx, layout.bottom_t_idx + 1)
    blocks = {
        "stage": _ProbeBlock(name="stage", row_slice=row_stage, col_slice=col_stage),
        "node_energy": _ProbeBlock(name="node_energy", row_slice=row_node, col_slice=col_node),
        "liquid_flow": _ProbeBlock(name="liquid_flow", row_slice=row_liquid, col_slice=layout.liquid_slice),
        "vapor_flow": _ProbeBlock(name="vapor_flow", row_slice=row_vapor, col_slice=layout.vapor_slice),
    }
    if bool(include_vapor_regularization):
        blocks["vapor_regularization"] = _ProbeBlock(
            name="vapor_regularization",
            row_slice=row_vreg,
            col_slice=layout.vapor_slice,
        )
    return blocks


def _slice_norm_ratio(J: np.ndarray, row_slice: slice, col_slice: slice) -> float:
    full = float(np.linalg.norm(np.asarray(J, dtype=float), ord="fro"))
    if not np.isfinite(full) or full <= 0.0:
        return 0.0
    block = np.asarray(J[row_slice, col_slice], dtype=float)
    return float(np.linalg.norm(block, ord="fro") / full)


def probe_mini8_simultaneous_conditioning(
    *,
    excel_path: str,
    thermo_mode: str = "table",
    thermo_table_path: str = r"cache\thermo_table.json",
    thermo_pool_workers: Optional[int] = None,
    thermo_pool_chunk_size: int = 4,
    jac_rel_step: float = 1.0e-6,
    liquid_target_relax: float = 1.0,
    vapor_target_relax: float = 0.25,
    vapor_regularization_weight: float = 0.0,
) -> Dict[str, Any]:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    provider, thermo_mode_used = _build_provider(
        col,
        thermo_mode=thermo_mode,
        thermo_table_path=thermo_table_path,
        thermo_pool_workers=thermo_pool_workers,
        thermo_pool_chunk_size=thermo_pool_chunk_size,
    )
    try:
        spec = build_mini8_uv_prototype_spec(excel_path=excel_path, provider=provider)
        y0 = _pack_state(
            spec.initial_total_component_holdup_lbmol,
            spec.initial_total_internal_energy_BTU,
            spec.top_node_reference.initial_component_holdup_lbmol,
            spec.bottom_node_reference.initial_component_holdup_lbmol,
            float(spec.top_node_reference.initial_total_internal_energy_BTU),
            float(spec.bottom_node_reference.initial_total_internal_energy_BTU),
        )
        z0 = default_algebraic_seed(spec=spec)
        eval0 = evaluate_simultaneous_algebraic_state(
            provider=provider,
            spec=spec,
            y=y0,
            z=z0,
            z_anchor=z0,
            liquid_target_relax=float(liquid_target_relax),
            vapor_target_relax=float(vapor_target_relax),
            vapor_regularization_weight=float(vapor_regularization_weight),
        )
        J = finite_difference_jacobian(
            lambda z_vec: evaluate_simultaneous_algebraic_state(
                provider=provider,
                spec=spec,
                y=y0,
                z=np.asarray(z_vec, dtype=float),
                z_anchor=z0,
                liquid_target_relax=float(liquid_target_relax),
                vapor_target_relax=float(vapor_target_relax),
                vapor_regularization_weight=float(vapor_regularization_weight),
            ).residual,
            z0,
            rel_step=float(jac_rel_step),
        )

        blocks = _build_probe_blocks(
            n_active=int(spec.active_stage0.size),
            n_total_stages=int(spec.n_total_stages),
            include_vapor_regularization=bool(float(vapor_regularization_weight) > 0.0),
        )
        block_metrics: Dict[str, Dict[str, float]] = {}
        cross_coupling: Dict[str, float] = {}
        for name, block in blocks.items():
            block_metrics[name] = _block_svd_metrics(J[block.row_slice, block.col_slice])
        for row_name, row_block in blocks.items():
            for col_name, col_block in blocks.items():
                if row_name == col_name:
                    continue
                key = f"{row_name}_to_{col_name}"
                cross_coupling[key] = _slice_norm_ratio(J, row_block.row_slice, col_block.col_slice)

        diag = eval0.diag or {}
        residual_summary = {
            "alg_inf": float(inf_norm(eval0.residual)),
            "raw_alg_inf": float(inf_norm(eval0.raw_residual)),
            "stage_scaled_inf": float(np.asarray(diag.get("simul_stage_scaled_inf", [np.nan]), dtype=float)[0]),
            "node_energy_scaled_inf": float(np.asarray(diag.get("simul_node_energy_scaled_inf", [np.nan]), dtype=float)[0]),
            "liquid_scaled_inf": float(np.asarray(diag.get("simul_lflow_scaled_inf", [np.nan]), dtype=float)[0]),
            "vapor_scaled_inf": float(np.asarray(diag.get("simul_vflow_scaled_inf", [np.nan]), dtype=float)[0]),
        }
        overall = _block_svd_metrics(J)
        return {
            "excel_path": str(excel_path),
            "thermo_mode": str(thermo_mode_used),
            "vapor_regularization_weight": float(vapor_regularization_weight),
            "n_active": int(spec.active_stage0.size),
            "n_total_stages": int(spec.n_total_stages),
            "jac_shape": [int(J.shape[0]), int(J.shape[1])],
            "overall_jacobian": overall,
            "residual_summary": residual_summary,
            "block_metrics": block_metrics,
            "cross_coupling_fro_ratio": cross_coupling,
            "recommendation": _recommend_probe_action(
                block_metrics=block_metrics,
                cross_coupling=cross_coupling,
                residual_summary=residual_summary,
            ),
        }
    finally:
        if hasattr(provider, "close") and callable(getattr(provider, "close")):
            try:
                provider.close()
            except Exception:
                pass


def _recommend_probe_action(
    *,
    block_metrics: Dict[str, Dict[str, float]],
    cross_coupling: Dict[str, float],
    residual_summary: Dict[str, float],
) -> str:
    vapor_cond = float(block_metrics.get("vapor_flow", {}).get("cond", float("nan")))
    vapor_scaled = float(residual_summary.get("vapor_scaled_inf", float("nan")))
    vapor_to_stage = float(cross_coupling.get("vapor_flow_to_stage", 0.0))
    if np.isfinite(vapor_cond) and vapor_cond >= 1.0e6:
        return "vapor_flow block is effectively singular; prioritize vapor regularization or dummy-derivative treatment"
    if np.isfinite(vapor_scaled) and vapor_scaled > 2.0:
        return "vapor_flow block dominates the residual; prioritize vapor regularization before broader DAE changes"
    if vapor_to_stage > 0.25:
        return "vapor_flow is strongly coupled to stage thermo; regularize vapor and stage blocks together"
    return "no single block dominates strongly at the seed state; broader residual scaling or better seeding may matter more"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Probe mini8 simultaneous residual conditioning.")
    p.add_argument(
        "--excel",
        dest="excel_path",
        default=r"sandbox/mini8/input/distillation_column_template_8stage.xlsx",
        help="Path to the sandbox workbook.",
    )
    p.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["auto", "dwsim", "table", "table-pool"],
        default="table",
    )
    p.add_argument("--thermo-table", dest="thermo_table_path", default=r"cache\thermo_table.json")
    p.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=None)
    p.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    p.add_argument("--jac-rel-step", dest="jac_rel_step", type=float, default=1.0e-6)
    p.add_argument("--liquid-target-relax", dest="liquid_target_relax", type=float, default=1.0)
    p.add_argument("--vapor-target-relax", dest="vapor_target_relax", type=float, default=0.25)
    p.add_argument("--vapor-regularization-weight", dest="vapor_regularization_weight", type=float, default=0.0)
    p.add_argument("--out", dest="out_path", default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    out = probe_mini8_simultaneous_conditioning(
        excel_path=str(args.excel_path),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=str(args.thermo_table_path),
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=int(args.thermo_pool_chunk_size),
        jac_rel_step=float(args.jac_rel_step),
        liquid_target_relax=float(args.liquid_target_relax),
        vapor_target_relax=float(args.vapor_target_relax),
        vapor_regularization_weight=float(args.vapor_regularization_weight),
    )
    payload = json.dumps(out, indent=2, sort_keys=True)
    if args.out_path:
        out_path = Path(str(args.out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
