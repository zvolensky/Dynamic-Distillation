#!/usr/bin/env python
"""Design DD-230 fixed coordinate scaling from DD-229's four saved matrices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import analyze_core_v3_dd223_conditioning as dd226


SOURCE = Path("logs/dd229_core_v3_aligned_pr_density_parity_20260815.json")
RESULT = Path("logs/dd230_core_v3_full_c3c4_coordinate_scaling_20260815")
SCHEMA = "dd230-core-v3-full-c3c4-coordinate-scaling-v1"
MAX_SCALE_RATIO = 1.0e8
MAX_SCALED_CONDITION = 1.0e8


def _condition(matrix: np.ndarray) -> float:
    singular = np.linalg.svd(matrix, compute_uv=False)
    return float(singular[0] / singular[-1])


def design_scale(matrices: Sequence[np.ndarray]) -> np.ndarray:
    """Use the geometric mean column norm across all accepted matrices."""
    norms = np.asarray(
        [np.maximum(np.linalg.norm(matrix, axis=0), 1.0e-15) for matrix in matrices]
    )
    aggregate = np.exp(np.mean(np.log(norms), axis=0))
    scale = 1.0 / aggregate
    scale /= float(np.exp(np.mean(np.log(scale))))
    if np.any(~np.isfinite(scale)) or np.any(scale <= 0.0):
        raise RuntimeError("DD-230 produced invalid coordinate scales")
    return scale


def _family_summary(names: Sequence[str], scale: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {}
    families = [dd226._family(name) for name in names]
    for family in sorted(set(families)):
        values = scale[np.asarray([item == family for item in families])]
        result[family] = {
            "count": int(values.size),
            "minimum": float(np.min(values)),
            "median": float(np.median(values)),
            "maximum": float(np.max(values)),
        }
    return result


def run(source_path: Path = SOURCE, out_prefix: Path = RESULT) -> dict[str, Any]:
    source = json.loads((ROOT / source_path).read_text(encoding="utf-8"))
    if not source.get("pass_gate"):
        raise RuntimeError("DD-230 requires the passing DD-229 result")
    evidence = np.load(ROOT / source["matrix_evidence"])
    matrix_keys = sorted(key for key in evidence.files if "jacobian" in key)
    matrices = [np.asarray(evidence[key], dtype=float) for key in matrix_keys]
    if len(matrices) != 4 or any(matrix.shape != (160, 160) for matrix in matrices):
        raise RuntimeError("DD-230 requires four complete 160 x 160 matrices")
    names = json.loads(
        (ROOT / "logs/dd229_core_v3_aligned_pr_density_parity_contract_20260815.json").read_text(
            encoding="utf-8"
        )
    )["coordinate_names"]
    scale = design_scale(matrices)
    comparisons = []
    for key, matrix in zip(matrix_keys, matrices, strict=True):
        original = _condition(matrix)
        scaled = _condition(matrix * scale[None, :])
        comparisons.append(
            {
                "matrix": key,
                "original_condition": original,
                "scaled_condition": scaled,
                "condition_improvement": float(original / scaled),
            }
        )
    scale_ratio = float(np.max(scale) / np.min(scale))
    pass_gate = bool(
        scale_ratio < MAX_SCALE_RATIO
        and all(item["scaled_condition"] < MAX_SCALED_CONDITION for item in comparisons)
        and all(item["condition_improvement"] > 1.0 for item in comparisons)
    )
    report = {
        "schema_id": SCHEMA,
        "classification": (
            "fixed_coordinate_scaling_passed"
            if pass_gate else "fixed_coordinate_scaling_failed"
        ),
        "decision": (
            "authorize_one_frozen_aligned_pr_density_stationary_root_campaign"
            if pass_gate else "stop_before_stationary_root_campaign"
        ),
        "method": "inverse_geometric_mean_column_norm_across_four_DD229_matrices",
        "coordinate_names": names,
        "coordinate_scale": scale.tolist(),
        "scale_ratio": scale_ratio,
        "family_summary": _family_summary(names, scale),
        "matrix_comparisons": comparisons,
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "timestep_calls": 0,
        "dynamic_integration_calls": 0,
        "pass_gate": pass_gate,
    }
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-prefix", type=Path, default=RESULT)
    args = parser.parse_args()
    report = run(args.source, args.out_prefix)
    print(json.dumps(report, indent=2))
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
