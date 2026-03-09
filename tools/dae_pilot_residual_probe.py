"""
dae_pilot_residual_probe.py

Run a single-step residual probe for the pilot simultaneous DAE formulation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

import numpy as np

# Allow direct "python tools/..." execution without external PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.dae_pilot_v1 import (
    default_algebraic_seed,
    evaluate_pilot_residual,
    finite_difference_jacobian,
    inf_norm,
)
from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, run_smoke_simulation


def _max_abs_index(arr: np.ndarray) -> int:
    a = np.asarray(arr, dtype=float).reshape((-1,))
    if a.size == 0 or not np.any(np.isfinite(a)):
        return -1
    return int(np.nanargmax(np.abs(a)))


def _json_print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    p = argparse.ArgumentParser(description="Pilot DAE residual probe")
    p.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    p.add_argument("--runtime-mode", dest="runtime_mode", default="hydraulic", choices=("legacy", "parity", "hydraulic"))
    p.add_argument("--thermo", dest="thermo_mode", default="table", choices=("stub", "dwsim", "table", "table-pool"))
    p.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    p.add_argument("--include-energy", action="store_true")
    p.add_argument("--dt", dest="dt_sec", type=float, default=0.2)
    p.add_argument("--pv-inner-max-iter", dest="pv_inner_max_iter", type=int, default=1)
    p.add_argument("--jacobian", action="store_true", help="Compute finite-difference algebraic Jacobian diagnostics")
    p.add_argument("--jacobian-rel-step", dest="jac_rel_step", type=float, default=1.0e-6)
    args = p.parse_args()

    cfg = RunnerConfig(
        excel_path=str(args.excel_path),
        n_steps=0,
        dt_sec=float(args.dt_sec),
        log_every_n_steps=1,
        runtime_mode=str(args.runtime_mode),
        include_temperature=True,
        include_energy=bool(args.include_energy),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=str(args.thermo_table_path) if args.thermo_table_path else None,
        pv_inner_max_iter=max(int(args.pv_inner_max_iter), 1),
        write_logs=False,
    )
    out = run_smoke_simulation(cfg)

    y0 = np.asarray(out["final_state"], dtype=float).reshape((-1,))
    col = out["column"]
    layout = out["layout"]
    inputs = out["inputs"]
    diag0 = out.get("last_diag", None)

    z0 = default_algebraic_seed(
        n_stages=int(col.n_stages),
        diag=diag0,
        p_fallback_psia=np.asarray(getattr(col, "P_psia"), dtype=float).reshape((col.n_stages,)),
        v_fallback_lbmolph=np.asarray(getattr(col, "V_lbmolph"), dtype=float).reshape((col.n_stages,)),
    )
    resid0 = evaluate_pilot_residual(
        t_s=0.0,
        y=y0,
        ydot=np.zeros_like(y0),
        z=z0,
        col=col,
        layout=layout,
        inputs=inputs,
    )
    resid_consistent = evaluate_pilot_residual(
        t_s=0.0,
        y=y0,
        ydot=resid0.dydt_rhs,
        z=z0,
        col=col,
        layout=layout,
        inputs=inputs,
    )

    idx_p = _max_abs_index(resid_consistent.alg_pressure)
    idx_v = _max_abs_index(resid_consistent.alg_vapor)
    payload: Dict[str, Any] = {
        "excel_path": str(args.excel_path),
        "runtime_mode": str(args.runtime_mode),
        "thermo_mode": str(args.thermo_mode),
        "n_stages": int(col.n_stages),
        "state_size": int(y0.size),
        "z_size": int(z0.size),
        "residual_norms": {
            "diff_inf": inf_norm(resid_consistent.diff),
            "alg_pressure_inf": inf_norm(resid_consistent.alg_pressure),
            "alg_vapor_inf": inf_norm(resid_consistent.alg_vapor),
            "full_inf": inf_norm(resid_consistent.full),
        },
        "largest_pressure_residual": {
            "stage_1based": (idx_p + 1) if idx_p >= 0 else None,
            "value": float(resid_consistent.alg_pressure[idx_p]) if idx_p >= 0 else None,
        },
        "largest_vapor_residual": {
            "stage_1based": (idx_v + 1) if idx_v >= 0 else None,
            "value_lbmolph": float(resid_consistent.alg_vapor[idx_v]) if idx_v >= 0 else None,
        },
    }

    if bool(args.jacobian):
        ydot_ref = resid0.dydt_rhs

        def g_of_z(z_trial: np.ndarray) -> np.ndarray:
            rr = evaluate_pilot_residual(
                t_s=0.0,
                y=y0,
                ydot=ydot_ref,
                z=z_trial,
                col=col,
                layout=layout,
                inputs=inputs,
            )
            return np.concatenate([rr.alg_pressure, rr.alg_vapor], axis=0)

        J = finite_difference_jacobian(g_of_z, z0, rel_step=float(args.jac_rel_step))
        sv = np.linalg.svd(J, compute_uv=False)
        sv_finite = sv[np.isfinite(sv)]
        if sv_finite.size > 0:
            s_max = float(np.max(sv_finite))
            s_min = float(np.min(sv_finite))
            cond = float(s_max / s_min) if s_min > 0.0 else float("inf")
        else:
            s_max = float("nan")
            s_min = float("nan")
            cond = float("nan")
        payload["jacobian"] = {
            "shape": [int(J.shape[0]), int(J.shape[1])],
            "inf_norm": inf_norm(J),
            "sigma_max": s_max,
            "sigma_min": s_min,
            "cond_est": cond,
        }

    _json_print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
