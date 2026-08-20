#!/usr/bin/env python
"""Freeze the single DD-245 stationary vapor-holdup root campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RESIDUAL = Path(
    "logs/dd243_core_v3_c3c4_vapor_holdup_stationary_residual_20260820.json"
)
SOURCE_JACOBIAN = Path(
    "logs/dd244_core_v3_c3c4_vapor_holdup_stationary_jacobian_20260820.json"
)
SOURCE_MATRIX = Path(
    "logs/dd244_core_v3_c3c4_vapor_holdup_stationary_jacobian_20260820.npz"
)
DEFAULT_CONTRACT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_contract_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_245_core_v3_c3c4_vapor_holdup_stationary_root_contract_20260820.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/vapor_holdup_stationary_contract_v1.py",
    "src/dynamic_distillation/core_v3/vapor_holdup_stationary_residual_v1.py",
    "src/dynamic_distillation/core_v3/vapor_holdup_properties_v1.py",
    "src/dynamic_distillation/core_v3/vapor_holdup_balances_v1.py",
    "tools/audit_core_v3_vapor_holdup_stationary_residual.py",
    "tools/run_core_v3_vapor_holdup_stationary_root.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _payload_sha(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def _bounds(dimension: int) -> tuple[np.ndarray, np.ndarray]:
    if dimension != 260:
        raise RuntimeError("DD-245 requires the frozen 260-coordinate ledger")
    lower = np.empty(dimension, dtype=float)
    upper = np.empty(dimension, dtype=float)
    lower[:120] = np.log(0.2)
    upper[:120] = np.log(5.0)
    lower[120:180] = -5.0
    upper[120:180] = 5.0
    lower[180:200] = -5.0
    upper[180:200] = 5.0
    lower[200:220] = -20.0
    upper[200:220] = 20.0
    lower[220:257] = np.log(0.2)
    upper[220:257] = np.log(5.0)
    lower[257:] = np.log(0.5)
    upper[257:] = np.log(1.5)
    return lower, upper


def build_contract() -> dict[str, Any]:
    residual = json.loads((ROOT / SOURCE_RESIDUAL).read_text(encoding="utf-8"))
    jacobian = json.loads((ROOT / SOURCE_JACOBIAN).read_text(encoding="utf-8"))
    if not residual.get("pass_gate") or not jacobian.get("pass_gate"):
        raise RuntimeError("DD-245 requires passing DD-243 and DD-244 evidence")
    if residual["dimension"] != 260 or jacobian["dimension"] != 260:
        raise RuntimeError("DD-245 source dimension changed")
    matrices = np.load(ROOT / SOURCE_MATRIX)
    column_norm_h1 = np.linalg.norm(matrices["jacobian_h1"], axis=0)
    column_norm_h2 = np.linalg.norm(matrices["jacobian_h2"], axis=0)
    geometric_norm = np.sqrt(column_norm_h1 * column_norm_h2)
    coordinate_scale = 1.0 / np.maximum(geometric_norm, 1.0e-30)
    coordinate_scale /= np.median(coordinate_scale)
    scaled_conditions = []
    for key in ("jacobian_h1", "jacobian_h2"):
        singular = np.linalg.svd(
            matrices[key] * coordinate_scale[np.newaxis, :],
            compute_uv=False,
        )
        scaled_conditions.append(float(singular[0] / singular[-1]))
    lower, upper = _bounds(260)
    payload: dict[str, Any] = {
        "schema_id": "dd245-core-v3-c3c4-vapor-holdup-stationary-root-contract-v1",
        "preparation_base_commit": _git_head(),
        "source_residual": str(SOURCE_RESIDUAL).replace("\\", "/"),
        "source_residual_sha256": _sha256(ROOT / SOURCE_RESIDUAL),
        "source_jacobian": str(SOURCE_JACOBIAN).replace("\\", "/"),
        "source_jacobian_sha256": _sha256(ROOT / SOURCE_JACOBIAN),
        "source_matrix": str(SOURCE_MATRIX).replace("\\", "/"),
        "source_matrix_sha256": _sha256(ROOT / SOURCE_MATRIX),
        "dimension": 260,
        "variable_names": residual["variable_names"],
        "start": [0.0] * 260,
        "lower_bounds": lower.tolist(),
        "upper_bounds": upper.tolist(),
        "coordinate_scale": coordinate_scale.tolist(),
        "coordinate_scale_method": (
            "inverse geometric-mean DD-244 Jacobian column norm, normalized by median"
        ),
        "coordinate_scale_range": [
            float(np.min(coordinate_scale)),
            float(np.max(coordinate_scale)),
        ],
        "source_scaled_conditions": scaled_conditions,
        "solver": {
            "method": "trf",
            "jacobian": "28-color central difference",
            "difference_step": 1.0e-5,
            "ftol": 1.0e-11,
            "xtol": 1.0e-11,
            "gtol": 1.0e-11,
            "max_nfev": 120,
        },
        "acceptance": {
            "scaled_residual_inf_norm": 1.0e-8,
            "endpoint_rank": 260,
            "endpoint_condition": 1.0e8,
            "endpoint_spectrum_relative_change": 0.25,
            "endpoint_matrix_relative_change": 0.05,
            "relative_eos_residual": 1.0e-10,
            "fugacity_residual": 1.0e-8,
            "component_balance_lbmolph": 1.0e-6,
            "energy_balance_BTUph": 1.0e-3,
            "pressure_residual_psia": 1.0e-8,
            "terminal_inventory_residual_lbmol": 1.0e-8,
            "minimum_bound_distance": 1.0e-6,
            "logical_provider_calls": 1_000_000,
            "wall_clock_sec": 600.0,
        },
        "hard_stops": [
            "one start and one least-squares execution only",
            "no retry, continuation, alternate solver, or tolerance change",
            "no clipping, projection, property fallback, or profile forcing",
            "reject nonphysical or unordered endpoint pressure",
            "reject failed conservation, EOS, equilibrium, rank, or conditioning",
            "dynamic timestep and integration remain prohibited",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION
        },
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _payload_sha(payload)
    return payload


def _markdown(contract: dict[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-245 Stationary Vapor-Holdup Root Contract",
            "",
            "- Starts: `1`",
            "- Solver: `scipy.optimize.least_squares(method='trf')`",
            "- Jacobian: `28-color central difference, h=1e-5`",
            "- Dimension: `260 x 260`",
            f"- Maximum function evaluations: `{contract['solver']['max_nfev']}`",
            (
                "- Fixed coordinate-scale range: "
                f"`{contract['coordinate_scale_range'][0]:.6g}` to "
                f"`{contract['coordinate_scale_range'][1]:.6g}`"
            ),
            (
                "- Source scaled conditions: "
                f"`{contract['source_scaled_conditions'][0]:.6e}` / "
                f"`{contract['source_scaled_conditions'][1]:.6e}`"
            ),
            "- Root residual limit: `1e-8`",
            "- Endpoint rank/condition: `260 / <1e8`",
            "- Call/wall limits: `1,000,000 / 600 s`",
            "",
            "The campaign has no retry or tuning path. Failure stops nonlinear work; "
            "success still requires a separate dynamic handoff and hold audit.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    contract = build_contract()
    contract_path = ROOT / args.contract
    doc_path = ROOT / args.doc
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    doc_path.write_text(_markdown(contract), encoding="utf-8")
    print(
        json.dumps(
            {
                "schema_id": contract["schema_id"],
                "dimension": contract["dimension"],
                "contract_payload_sha256": contract["contract_payload_sha256"],
                "nonlinear_solve_attempted": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
