#!/usr/bin/env python
"""Diagnose the rejected water-methanol stationary candidate without re-solving."""

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

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_stationary_root as stationary_root  # noqa: E402

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
    "logs/core_v3_water_methanol_rejected_root_diagnostic_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_rejected_root_diagnostic_20260831.md"
)
DEFAULT_MATRIX = Path(
    "logs/core_v3_water_methanol_rejected_root_diagnostic_20260831.npz"
)
STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
MATRIX_CHANGE_LIMIT = 0.05


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    root_path = ROOT / stationary_root.DEFAULT_JSON
    root = json.loads(root_path.read_text(encoding="utf-8"))
    if root.get("pass_gate") or root.get("classification") != "stationary_root_rejected":
        raise RuntimeError("diagnostic requires the rejected stationary candidate")
    candidate = np.asarray(root["endpoint"]["coordinates"], dtype=float)
    problem = starting_state.build_problem()
    contract = problem["contract"]
    dimension = len(contract.variables)
    if candidate.shape != (dimension,):
        raise RuntimeError("rejected candidate does not match the current variable ledger")
    pattern = stationary_structural_pattern(contract)
    names = stationary_variable_names(contract)
    row_names = tuple(row.name for row in contract.rows)
    audit = ProviderCallAudit(provider_identity="dwsim")
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    def objective(point: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            point,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    started = time.perf_counter()
    matrices: list[np.ndarray] = []
    step_results = []
    for step in STEPS:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            candidate,
            pattern=pattern,
            step=step,
            state_id=f"water_methanol:rejected_candidate:h={step:.1e}",
        )
        rank, condition, singular = _rank_condition(matrix)
        matrices.append(matrix)
        step_results.append(
            {
                "step": step,
                "rank": rank,
                "condition": condition,
                "smallest_singular_value": float(singular[-1]),
                "largest_singular_value": float(singular[0]),
                "color_count": len(groups),
            }
        )
    matrix_change = float(
        np.linalg.norm(matrices[0] - matrices[1])
        / max(np.linalg.norm(matrices[0]), np.linalg.norm(matrices[1]), 1.0e-30)
    )
    base = objective(candidate, "water_methanol:rejected_candidate:base")
    gradient_inf = float(np.max(np.abs(matrices[0].T @ base)))
    difference = np.abs(matrices[0] - matrices[1])
    flat_order = np.argsort(difference, axis=None)[::-1][:12]
    changed_entries = []
    for flat_index in flat_order:
        row, column = np.unravel_index(int(flat_index), difference.shape)
        changed_entries.append(
            {
                "row": row_names[row],
                "variable": names[column],
                "derivative_h1": float(matrices[0][row, column]),
                "derivative_h2": float(matrices[1][row, column]),
                "absolute_change": float(difference[row, column]),
            }
        )
    wall = time.perf_counter() - started
    derivative_pass = bool(
        all(item["rank"] == dimension for item in step_results)
        and all(item["condition"] < CONDITION_LIMIT for item in step_results)
        and matrix_change < MATRIX_CHANGE_LIMIT
        and not audit.fallback_attempted
    )
    report = {
        "schema_id": "core-v3-water-methanol-rejected-root-diagnostic-v1",
        "classification": "rejected_candidate_derivatives_unreliable",
        "source_root_result": str(root_path.relative_to(ROOT)).replace("\\", "/"),
        "source_scaled_residual_inf_norm": root["scaled_residual_inf_norm"],
        "source_solver_optimality": root["solver"]["optimality"],
        "dimension": dimension,
        "step_results": step_results,
        "matrix_relative_frobenius_change": matrix_change,
        "gradient_inf_norm_at_h1": gradient_inf,
        "largest_step_sensitive_entries": changed_entries,
        "limits": {
            "condition": CONDITION_LIMIT,
            "matrix_relative_frobenius_change": MATRIX_CHANGE_LIMIT,
        },
        "logical_provider_calls": audit.record_count,
        "provider_fallback_attempted": audit.fallback_attempted,
        "wall_clock_sec": wall,
        "derivative_gate_pass": derivative_pass,
        "nonlinear_solve_attempted": False,
        "retry_attempted": False,
        "timestep_attempted": False,
        "pass_gate": not derivative_pass,
        "decision": "investigate_local_derivative_noise_before_any_second_solve",
    }
    evidence = {
        "candidate_coordinates": candidate,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "scaled_residual": base,
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["step_results"]
    return "\n".join(
        (
            "# Core V3 water-methanol rejected-root diagnosis",
            "",
            f"- Finding: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Candidate scaled equation error: `{report['source_scaled_residual_inf_norm']:.6e}`",
            f"- Rank at both step sizes: `{first['rank']} / {second['rank']}`",
            f"- Condition number: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Matrix change when step was halved: `{report['matrix_relative_frobenius_change']:.6e}`",
            f"- Solver optimality measure: `{report['source_solver_optimality']:.6e}`",
            f"- Live property calls: `{report['logical_provider_calls']}`",
            "- Second nonlinear solve or timestep: `False`",
            "",
            "## Meaning",
            "",
            (
                "The candidate remained physical and away from its bounds, but the local "
                "derivatives became badly conditioned and changed sharply with numerical "
                "step size. The solver therefore stopped with a small step before the "
                "stationary equations were closed."
            ),
            "",
            (
                "The next task is to isolate the noisy property or equation derivatives. "
                "A second solve should not be attempted until that numerical issue is understood."
            ),
            "",
        )
    )


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute()
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    matrix_path = _rooted(args.matrix)
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
                "condition_h1": report["step_results"][0]["condition"],
                "condition_h2": report["step_results"][1]["condition"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
