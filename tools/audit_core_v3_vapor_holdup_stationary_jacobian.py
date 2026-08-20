#!/usr/bin/env python
"""Audit the stationary vapor-holdup Jacobian at two fixed difference steps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_vapor_holdup_stationary_residual as dd243  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
    stationary_variable_names,
)


DEFAULT_JSON = Path(
    "logs/dd244_core_v3_c3c4_vapor_holdup_stationary_jacobian_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_244_core_v3_c3c4_vapor_holdup_stationary_jacobian_20260820.md"
)
DEFAULT_MATRIX = Path(
    "logs/dd244_core_v3_c3c4_vapor_holdup_stationary_jacobian_20260820.npz"
)
STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
MATRIX_CHANGE_LIMIT = 0.05
SENTINEL_ABSOLUTE_LIMIT = 1.0e-7
SENTINEL_RELATIVE_LIMIT = 1.0e-5
CALL_LIMIT = 30000
WALL_LIMIT_SEC = 180.0


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(
        float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30
    )
    return float(np.linalg.norm(left - right) / denominator)


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    problem = dd243.build_problem()
    contract = problem["contract"]
    dimension = len(contract.variables)
    point = np.zeros(dimension)
    pattern = stationary_structural_pattern(contract)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            candidate,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    started = time.perf_counter()
    matrices: list[np.ndarray] = []
    step_results: list[dict[str, Any]] = []
    groups_reference: tuple[tuple[int, ...], ...] | None = None
    variable_names = stationary_variable_names(contract)
    for step in STEPS:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=step,
            state_id=f"dd244:h={step:.1e}",
        )
        if groups_reference is None:
            groups_reference = groups
        elif groups != groups_reference:
            raise RuntimeError("DD-244 coloring changed between difference steps")
        rank, condition, singular = _rank_condition(matrix)
        row_norm = np.linalg.norm(matrix, axis=1)
        column_norm = np.linalg.norm(matrix, axis=0)
        matrices.append(matrix)
        step_results.append(
            {
                "step": step,
                "rank": rank,
                "condition": condition,
                "singular_values": [float(value) for value in singular],
                "zero_rows": [
                    contract.rows[index].name
                    for index in np.flatnonzero(row_norm <= 1.0e-12)
                ],
                "zero_columns": [
                    variable_names[index]
                    for index in np.flatnonzero(column_norm <= 1.0e-12)
                ],
            }
        )

    sentinel_columns = (0, 60, 120, 180, 200, 220, 238, 257, 258, 259)
    sentinel_results = []
    direct_step = STEPS[0]
    for column in sentinel_columns:
        delta = np.zeros(dimension)
        delta[column] = direct_step
        direct = (
            objective(point + delta, f"dd244:sentinel:{column}:plus")
            - objective(point - delta, f"dd244:sentinel:{column}:minus")
        ) / (2.0 * direct_step)
        colored = matrices[0][:, column]
        absolute = float(np.max(np.abs(direct - colored)))
        relative = _relative_change(direct, colored)
        outside = float(np.max(np.abs(direct[~pattern[:, column]])))
        sentinel_results.append(
            {
                "column": int(column),
                "variable": variable_names[column],
                "maximum_absolute_difference": absolute,
                "relative_l2_difference": relative,
                "maximum_off_pattern_derivative": outside,
                "pass_gate": bool(
                    absolute <= SENTINEL_ABSOLUTE_LIMIT
                    and relative <= SENTINEL_RELATIVE_LIMIT
                    and outside <= SENTINEL_ABSOLUTE_LIMIT
                ),
            }
        )
    wall = time.perf_counter() - started
    spectrum_change = _relative_change(
        np.asarray(step_results[0]["singular_values"]),
        np.asarray(step_results[1]["singular_values"]),
    )
    matrix_change = _relative_change(matrices[0], matrices[1])
    memo = (
        provider.get_exact_state_memoization_stats()
        if hasattr(provider, "get_exact_state_memoization_stats")
        else {}
    )
    passed = bool(
        all(result["rank"] == dimension for result in step_results)
        and all(result["condition"] < CONDITION_LIMIT for result in step_results)
        and all(not result["zero_rows"] for result in step_results)
        and all(not result["zero_columns"] for result in step_results)
        and spectrum_change <= SPECTRUM_CHANGE_LIMIT
        and matrix_change <= MATRIX_CHANGE_LIMIT
        and all(result["pass_gate"] for result in sentinel_results)
        and audit.record_count <= CALL_LIMIT
        and wall <= WALL_LIMIT_SEC
        and not audit.fallback_attempted
    )
    report = {
        "schema_id": "dd244-core-v3-c3c4-vapor-holdup-stationary-jacobian-v1",
        "classification": (
            "vapor_holdup_stationary_jacobian_passed"
            if passed
            else "vapor_holdup_stationary_jacobian_failed"
        ),
        "dimension": dimension,
        "difference_steps": list(STEPS),
        "color_count": len(groups_reference or ()),
        "color_groups": [list(group) for group in (groups_reference or ())],
        "step_results": step_results,
        "spectrum_relative_change": spectrum_change,
        "matrix_relative_frobenius_change": matrix_change,
        "sentinel_columns": sentinel_results,
        "limits": {
            "condition": CONDITION_LIMIT,
            "spectrum_relative_change": SPECTRUM_CHANGE_LIMIT,
            "matrix_relative_frobenius_change": MATRIX_CHANGE_LIMIT,
            "sentinel_absolute": SENTINEL_ABSOLUTE_LIMIT,
            "sentinel_relative": SENTINEL_RELATIVE_LIMIT,
            "logical_provider_calls": CALL_LIMIT,
            "wall_clock_sec": WALL_LIMIT_SEC,
        },
        "logical_provider_calls": audit.record_count,
        "memoization": memo,
        "wall_clock_sec": wall,
        "provider_fallback_attempted": audit.fallback_attempted,
        "nonlinear_solve_attempted": False,
        "timestep_accepted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_one_bounded_stationary_vapor_holdup_root_campaign"
            if passed
            else "stop_stationary_vapor_holdup_nonlinear_work"
        ),
    }
    evidence = {
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["step_results"]
    return "\n".join(
        (
            "# DD-244 Stationary Vapor-Holdup Jacobian",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Dimension/colors: `{report['dimension']} / {report['color_count']}`",
            f"- Rank at h1/h2: `{first['rank']} / {second['rank']}`",
            (
                "- Condition at h1/h2: "
                f"`{first['condition']:.6e} / {second['condition']:.6e}`"
            ),
            f"- Spectrum relative change: `{report['spectrum_relative_change']:.6e}`",
            (
                "- Matrix relative change: "
                f"`{report['matrix_relative_frobenius_change']:.6e}`"
            ),
            (
                "- Sentinel columns passed: "
                f"`{sum(item['pass_gate'] for item in report['sentinel_columns'])}/"
                f"{len(report['sentinel_columns'])}`"
            ),
            f"- Logical provider calls: `{report['logical_provider_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            "",
            "No nonlinear solve, accepted timestep, or integration occurred.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute()
    json_path = ROOT / args.json
    doc_path = ROOT / args.doc
    matrix_path = ROOT / args.matrix
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(matrix_path, **evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
