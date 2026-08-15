#!/usr/bin/env python
"""Localize DD-223 conditioning from DD-225's saved matrices with zero live calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("logs/dd225_core_v3_dd223_endpoint_replay_20260815.json")
RESULT = Path("logs/dd226_core_v3_dd223_conditioning_localization_20260815")
SCHEMA = "dd226-core-v3-dd223-conditioning-localization-v1"


def _family(name: str) -> str:
    if name.startswith("log_NL["):
        return "liquid_inventory"
    if name.startswith("x_alr["):
        return "liquid_composition"
    if name.startswith("T["):
        return "temperature"
    if name.startswith("y_alr["):
        return "vapor_composition"
    if name.startswith("log_L["):
        return "liquid_flow"
    if name.startswith("log_V"):
        return "vapor_flow"
    if name == "log_D":
        return "distillate_flow"
    if name == "log_B":
        return "bottoms_flow"
    if name.startswith("y_bubble_alr["):
        return "condenser_bubble_composition"
    if name == "q_Q_C":
        return "condenser_duty"
    return "other"


def _owner(name: str) -> str:
    match = re.search(r"\[([^,\]]+)", name)
    return match.group(1) if match else "column_boundary"


def _shares(vector: np.ndarray, labels: Sequence[str]) -> dict[str, float]:
    weights = np.asarray(vector, dtype=float) ** 2
    total = float(np.sum(weights))
    grouped: dict[str, float] = {}
    for weight, label in zip(weights, labels, strict=True):
        grouped[label] = grouped.get(label, 0.0) + float(weight) / total
    return dict(sorted(grouped.items(), key=lambda item: item[1], reverse=True))


def _top(vector: np.ndarray, names: Sequence[str], count: int = 12) -> list[dict[str, Any]]:
    indices = np.argsort(np.abs(vector))[::-1][:count]
    return [
        {
            "index": int(index),
            "name": names[int(index)],
            "value": float(vector[int(index)]),
            "absolute": float(abs(vector[int(index)])),
        }
        for index in indices
    ]


def _condition(matrix: np.ndarray) -> float:
    singular = np.linalg.svd(matrix, compute_uv=False)
    return float(singular[0] / singular[-1])


def _equilibrated_condition(matrix: np.ndarray, iterations: int = 12) -> dict[str, float]:
    balanced = np.asarray(matrix, dtype=float).copy()
    row_scale = np.ones(balanced.shape[0])
    column_scale = np.ones(balanced.shape[1])
    floor = np.finfo(float).tiny
    for _ in range(iterations):
        row_norm = np.maximum(np.linalg.norm(balanced, axis=1), floor)
        factor = 1.0 / np.sqrt(row_norm)
        balanced *= factor[:, None]
        row_scale *= factor
        column_norm = np.maximum(np.linalg.norm(balanced, axis=0), floor)
        factor = 1.0 / np.sqrt(column_norm)
        balanced *= factor[None, :]
        column_scale *= factor
    return {
        "condition": _condition(balanced),
        "row_scale_min": float(np.min(row_scale)),
        "row_scale_max": float(np.max(row_scale)),
        "column_scale_min": float(np.min(column_scale)),
        "column_scale_max": float(np.max(column_scale)),
    }


def _matrix_analysis(
    matrix: np.ndarray,
    residual: np.ndarray,
    coordinate_names: Sequence[str],
    residual_names: Sequence[str],
    residual_blocks: Sequence[str],
) -> dict[str, Any]:
    left, singular, right_t = np.linalg.svd(matrix, full_matrices=False)
    right = right_t[-1]
    weak_left = left[:, -1]
    correction_coefficients = -(left.T @ residual) / singular
    correction = right_t.T @ correction_coefficients
    original_condition = float(singular[0] / singular[-1])
    equilibrated = _equilibrated_condition(matrix)
    return {
        "condition": original_condition,
        "largest_singular_value": float(singular[0]),
        "smallest_singular_value": float(singular[-1]),
        "weak_coordinate_family_shares": _shares(
            right, [_family(name) for name in coordinate_names]
        ),
        "weak_coordinate_owner_shares": _shares(
            right, [_owner(name) for name in coordinate_names]
        ),
        "weak_residual_block_shares": _shares(weak_left, residual_blocks),
        "weak_residual_owner_shares": _shares(
            weak_left, [_owner(name) for name in residual_names]
        ),
        "top_weak_coordinates": _top(right, coordinate_names),
        "top_weak_residual_rows": _top(weak_left, residual_names),
        "linearized_correction_inf_norm": float(np.max(np.abs(correction))),
        "top_linearized_correction_coordinates": _top(correction, coordinate_names),
        "equilibrated": equilibrated,
        "equilibration_condition_improvement": float(
            original_condition / equilibrated["condition"]
        ),
    }


def _step_comparison(
    first: np.ndarray,
    second: np.ndarray,
    coordinate_names: Sequence[str],
    residual_names: Sequence[str],
) -> dict[str, Any]:
    left_1, singular_1, right_t_1 = np.linalg.svd(first, full_matrices=False)
    left_2, singular_2, right_t_2 = np.linalg.svd(second, full_matrices=False)
    difference = second - first
    row, column = np.unravel_index(np.argmax(np.abs(difference)), difference.shape)
    relative_frobenius = float(
        np.linalg.norm(difference) / max(np.linalg.norm(first), 1.0e-30)
    )
    weak_count = 5
    weak_right_overlap = right_t_1[-weak_count:] @ right_t_2[-weak_count:].T
    weak_left_overlap = left_1[:, -weak_count:].T @ left_2[:, -weak_count:]
    return {
        "relative_frobenius_difference": relative_frobenius,
        "maximum_entry_difference": float(difference[row, column]),
        "maximum_entry_difference_absolute": float(abs(difference[row, column])),
        "maximum_difference_residual": residual_names[int(row)],
        "maximum_difference_coordinate": coordinate_names[int(column)],
        "largest_singular_value_ratio_second_over_first": float(
            singular_2[0] / singular_1[0]
        ),
        "smallest_singular_value_ratio_second_over_first": float(
            singular_2[-1] / singular_1[-1]
        ),
        "weakest_right_vector_alignment": float(abs(right_t_1[-1] @ right_t_2[-1])),
        "weakest_left_vector_alignment": float(abs(left_1[:, -1] @ left_2[:, -1])),
        "five_weakest_right_subspace_minimum_cosine": float(
            np.min(np.linalg.svd(weak_right_overlap, compute_uv=False))
        ),
        "five_weakest_left_subspace_minimum_cosine": float(
            np.min(np.linalg.svd(weak_left_overlap, compute_uv=False))
        ),
    }


def run(source_path: Path = SOURCE, out_prefix: Path = RESULT) -> dict[str, Any]:
    source = json.loads((ROOT / source_path).read_text(encoding="utf-8"))
    if not source.get("pass_gate") or not source.get("complete_evidence_saved"):
        raise RuntimeError("DD-226 requires the passing complete DD-225 evidence")
    coordinate_names = source["coordinate_names"]
    residual_names = source["residual_names"]
    residual_blocks = source["residual_blocks"]
    endpoint_reports: dict[str, Any] = {}
    for name, endpoint in source["endpoints"].items():
        residual = np.asarray(endpoint["scaled_residual"], dtype=float)
        matrices = [
            np.asarray(item["matrix"], dtype=float) for item in endpoint["jacobians"]
        ]
        matrix_reports = [
            _matrix_analysis(
                matrix,
                residual,
                coordinate_names,
                residual_names,
                residual_blocks,
            )
            for matrix in matrices
        ]
        top_residuals = _top(residual, residual_names, count=15)
        for item in top_residuals:
            item["block"] = residual_blocks[item["index"]]
        comparison = _step_comparison(
            matrices[0], matrices[1], coordinate_names, residual_names
        )
        endpoint_reports[name] = {
            "scaled_residual_inf_norm": float(np.max(np.abs(residual))),
            "top_scaled_residual_rows": top_residuals,
            "matrices": matrix_reports,
            "finite_difference_step_comparison": comparison,
        }

    worst_condition = max(
        matrix["condition"]
        for endpoint in endpoint_reports.values()
        for matrix in endpoint["matrices"]
    )
    best_equilibrated_condition = min(
        matrix["equilibrated"]["condition"]
        for endpoint in endpoint_reports.values()
        for matrix in endpoint["matrices"]
    )
    worst_step_difference = max(
        endpoint["finite_difference_step_comparison"]["relative_frobenius_difference"]
        for endpoint in endpoint_reports.values()
    )
    minimum_weak_alignment = min(
        endpoint["finite_difference_step_comparison"]["weakest_right_vector_alignment"]
        for endpoint in endpoint_reports.values()
    )
    scaling_material = bool(
        best_equilibrated_condition < 1.0e8
        and any(
            matrix["equilibration_condition_improvement"] > 10.0
            for endpoint in endpoint_reports.values()
            for matrix in endpoint["matrices"]
        )
    )
    finite_difference_instability = bool(
        worst_step_difference > 0.1 or minimum_weak_alignment < 0.8
    )
    if finite_difference_instability and scaling_material:
        diagnosis = "mixed_scaling_and_nonsmooth_derivative_problem"
        decision = "design_a_bounded_derivative_and_scaling_correction_before_any_new_root_solve"
    elif finite_difference_instability:
        diagnosis = "nonsmooth_or_unreliable_finite_difference_derivative_problem"
        decision = "localize_and_replace_the_unstable_derivative_path_before_any_new_root_solve"
    elif scaling_material:
        diagnosis = "coordinate_scaling_problem"
        decision = "design_fixed_coordinate_scaling_before_any_new_root_solve"
    else:
        diagnosis = "strong_physical_coupling_or_near_singular_equation_problem"
        decision = "review_the_identified_equation_closure_before_any_new_root_solve"
    report = {
        "schema_id": SCHEMA,
        "source": str(source_path).replace("\\", "/"),
        "classification": "dd223_conditioning_localized",
        "diagnosis": diagnosis,
        "decision": decision,
        "worst_condition": worst_condition,
        "best_equilibrated_condition": best_equilibrated_condition,
        "worst_step_relative_frobenius_difference": worst_step_difference,
        "minimum_weakest_right_vector_alignment": minimum_weak_alignment,
        "coordinate_scaling_material": scaling_material,
        "finite_difference_instability": finite_difference_instability,
        "endpoints": endpoint_reports,
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "timestep_calls": 0,
        "dynamic_integration_calls": 0,
        "pass_gate": True,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
