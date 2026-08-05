#!/usr/bin/env python
"""Prepare or execute the property-free DD-137 solver-capture audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    CapturedModifiedNewtonOutcome,
    solve_captured_modified_newton,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings


SCHEMA = "dd137-core-v3-captured-modified-newton-contract-v1"
RESULT_SCHEMA = "dd137-core-v3-captured-modified-newton-result-v1"
DD136_CONTRACT = Path("logs/dd136_core_v3_dd134_residual_replay_contract_20260805.json")
DD136_RESULT = Path("logs/dd136_core_v3_dd134_residual_replay_20260805.json")
CONTRACT = Path("logs/dd137_core_v3_captured_modified_newton_contract_20260805.json")
RESULT = Path("logs/dd137_core_v3_captured_modified_newton_20260805.json")
CONTRACT_DOC = Path("docs/dd_137_core_v3_captured_modified_newton_contract_20260805.md")
RESULT_DOC = Path("docs/dd_137_core_v3_captured_modified_newton_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/captured_modified_newton_v1.py",
    "src/dynamic_distillation/core_v3/modified_newton_v1.py",
    "tests/test_core_v3_captured_modified_newton_v1.py",
    "tools/audit_core_v3_captured_modified_newton.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def prepare() -> dict[str, Any]:
    source = _load(DD136_RESULT)
    dd134 = _load(
        Path("logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json")
    )
    if (
        not source["pass"]
        or source["classification"]
        != "deterministic_replay_dd134_artifact_incomplete"
        or source["decision"]
        != "authorize_separately_frozen_in_process_failure_capture_contract"
    ):
        raise RuntimeError("DD-137 requires the immutable passed DD-136 result")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD136_CONTRACT, DD136_RESULT)
        },
        "source_classification": source["classification"],
        "algorithm": dd134["algorithm"],
        "fixtures": {
            "full_rank_linear_dimension": 50,
            "line_search_failure_dimension": 1,
            "shared_buffer_alias_dimension": 1,
            "bounded_boundary_dimension": 1,
            "rank_failure_dimension": 2,
        },
        "capture_requirements": [
            "immutable independent copies of initial/final coordinates and residuals",
            "immutable frozen Jacobian with rank and condition",
            "immutable coordinates, residual, correction, and trial vectors per iteration",
            "fraction, state id, bounds status, Armijo limit, residual norm, and acceptance per trial",
            "final solver residual versus retained evaluation residual identity metric",
            "final solver coordinates versus retained evaluation coordinates identity metric",
            "explicit detection of a deliberately shared and mutated evaluation buffer",
        ],
        "identity_limit": 0.0,
        "alias_detection_minimum": 0.1,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-136 source or DD-137 implementation hash changes",
            "the historical modified_newton_v1 implementation is edited rather than versioned",
            "a captured array remains writeable or aliases later objective output",
            "a line-search fraction, bounds rejection, state id, residual, correction, Armijo decision, rank, condition, or counter is omitted",
            "the shared-buffer fixture is not detected by both final identity metrics",
            "a live property, column residual/Jacobian, nonlinear column solve, state advance, timestep, or trajectory is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "live_column_residual_attempted": False,
        "live_column_jacobian_attempted": False,
        "nonlinear_column_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-137 Frozen Captured Modified-Newton Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Historical solver modification: `False`",
                "- New versioned capture solver: `captured_modified_newton_v1`",
                "- Property-free fixtures: full-rank success, complete line-search failure, shared-buffer alias, bounded boundary, and rank failure",
                "- Immutable evidence: coordinates, residuals, Jacobian, correction, every trial, and final identity metrics",
                "- Live provider, column residual/Jacobian, column solve, timestep, and trajectory: prohibited",
                "",
                "Passing authorizes only a separately frozen live in-process failure-capture diagnostic contract.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-137 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-137 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-137 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-137 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _evaluation(point, residual) -> SimpleNamespace:
    return SimpleNamespace(
        scaled=np.asarray(residual, dtype=float).copy(),
        solve_coordinates=np.asarray(point, dtype=float).copy(),
    )


def _all_capture_arrays(outcome: CapturedModifiedNewtonOutcome) -> list[np.ndarray]:
    arrays = [
        outcome.initial_coordinates,
        outcome.initial_residual,
        outcome.final_coordinates,
        outcome.final_residual,
        outcome.final_evaluation_residual_at_return,
    ]
    if outcome.frozen_jacobian is not None:
        arrays.append(outcome.frozen_jacobian)
    if outcome.final_evaluation_coordinates_at_return is not None:
        arrays.append(outcome.final_evaluation_coordinates_at_return)
    for iteration in outcome.iteration_captures:
        arrays.extend(
            (
                iteration.coordinates_before,
                iteration.residual_before,
                iteration.correction,
            )
        )
        for trial in iteration.trials:
            arrays.append(trial.coordinates)
            if trial.residual is not None:
                arrays.append(trial.residual)
            if trial.evaluation_coordinates is not None:
                arrays.append(trial.evaluation_coordinates)
    return arrays


def _record(outcome: CapturedModifiedNewtonOutcome) -> dict[str, Any]:
    return {
        "success": outcome.success,
        "message": outcome.message,
        "iterations": outcome.iterations,
        "residual_evaluations": outcome.residual_evaluations,
        "jacobian_evaluations": outcome.jacobian_evaluations,
        "linear_solves": outcome.linear_solves,
        "accepted_steps": outcome.accepted_steps,
        "rejected_line_search_steps": outcome.rejected_line_search_steps,
        "rejected_bound_steps": outcome.rejected_bound_steps,
        "initial_coordinates": outcome.initial_coordinates.tolist(),
        "initial_residual": outcome.initial_residual.tolist(),
        "frozen_jacobian": (
            None if outcome.frozen_jacobian is None else outcome.frozen_jacobian.tolist()
        ),
        "jacobian_rank": outcome.jacobian_rank,
        "jacobian_condition": outcome.jacobian_condition,
        "final_coordinates": outcome.final_coordinates.tolist(),
        "final_residual": outcome.final_residual.tolist(),
        "final_evaluation_residual_at_return": outcome.final_evaluation_residual_at_return.tolist(),
        "final_evaluation_coordinates_at_return": (
            None
            if outcome.final_evaluation_coordinates_at_return is None
            else outcome.final_evaluation_coordinates_at_return.tolist()
        ),
        "final_residual_vs_evaluation_max_abs": outcome.final_residual_vs_evaluation_max_abs,
        "final_coordinates_vs_evaluation_max_abs": outcome.final_coordinates_vs_evaluation_max_abs,
        "all_capture_arrays_read_only": all(
            not array.flags.writeable for array in _all_capture_arrays(outcome)
        ),
        "iteration_captures": [
            {
                "iteration": item.iteration,
                "coordinates_before": item.coordinates_before.tolist(),
                "residual_before": item.residual_before.tolist(),
                "residual_inf_norm_before": item.residual_inf_norm_before,
                "correction": item.correction.tolist(),
                "trials": [
                    {
                        "iteration": trial.iteration,
                        "search_index": trial.search_index,
                        "fraction": trial.fraction,
                        "state_id": trial.state_id,
                        "coordinates": trial.coordinates.tolist(),
                        "within_bounds": trial.within_bounds,
                        "residual": None if trial.residual is None else trial.residual.tolist(),
                        "residual_inf_norm": trial.residual_inf_norm,
                        "armijo_limit": trial.armijo_limit,
                        "armijo_accepted": trial.armijo_accepted,
                        "evaluation_coordinates": (
                            None
                            if trial.evaluation_coordinates is None
                            else trial.evaluation_coordinates.tolist()
                        ),
                    }
                    for trial in item.trials
                ],
            }
            for item in outcome.iteration_captures
        ],
    }


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    settings = ModifiedNewtonSettings(
        **{
            key: payload["algorithm"][key]
            for key in (
                "residual_tolerance",
                "max_iterations",
                "line_search_fractions",
                "armijo_fraction",
                "condition_limit",
            )
        }
    )
    dimension = payload["fixtures"]["full_rank_linear_dimension"]
    initial = np.linspace(-2.0, 2.0, dimension)
    full_rank = solve_captured_modified_newton(
        lambda point, _state_id: _evaluation(point, point),
        lambda _point, _state_id: np.eye(dimension),
        initial,
        settings,
        name="dd137:full_rank",
    )
    line_failure = solve_captured_modified_newton(
        lambda point, _state_id: _evaluation(point, point),
        lambda _point, _state_id: np.asarray([[-1.0]]),
        [1.0],
        settings,
        name="dd137:line_failure",
    )

    shared_residual = np.zeros(1)
    shared_evaluation = SimpleNamespace(
        scaled=shared_residual,
        solve_coordinates=np.zeros(1),
    )

    def alias_objective(point, _state_id):
        shared_residual[:] = point
        shared_evaluation.solve_coordinates[:] = point
        return shared_evaluation

    alias = solve_captured_modified_newton(
        alias_objective,
        lambda _point, _state_id: np.asarray([[-1.0]]),
        [1.0],
        settings,
        name="dd137:alias",
    )

    def boundary_objective(point, _state_id):
        return _evaluation(point, np.asarray(point) - 0.75)

    bounded = solve_captured_modified_newton(
        boundary_objective,
        lambda _point, _state_id: np.asarray([[0.25]]),
        [1.0],
        settings,
        lower_bounds=[0.75],
        upper_bounds=[2.0],
        name="dd137:bounds",
    )
    rank_failure = solve_captured_modified_newton(
        lambda point, _state_id: _evaluation(point, point),
        lambda _point, _state_id: np.zeros((2, 2)),
        [1.0, 1.0],
        settings,
        name="dd137:rank",
    )
    outcomes = {
        "full_rank": _record(full_rank),
        "line_failure": _record(line_failure),
        "alias": _record(alias),
        "bounded": _record(bounded),
        "rank_failure": _record(rank_failure),
    }
    fractions = list(settings.line_search_fractions)
    gates = {
        "full_rank_success": bool(
            full_rank.success
            and full_rank.jacobian_rank == dimension
            and full_rank.final_residual_inf_norm == 0.0
            and full_rank.final_residual_vs_evaluation_max_abs == 0.0
            and full_rank.final_coordinates_vs_evaluation_max_abs == 0.0
        ),
        "line_failure_complete": bool(
            not line_failure.success
            and line_failure.message == "line search failed with frozen Jacobian"
            and line_failure.rejected_line_search_steps == len(fractions)
            and [trial.fraction for trial in line_failure.iteration_captures[0].trials]
            == fractions
            and not any(
                trial.armijo_accepted
                for trial in line_failure.iteration_captures[0].trials
            )
        ),
        "alias_detected": bool(
            alias.final_residual_vs_evaluation_max_abs
            >= payload["alias_detection_minimum"]
            and alias.final_coordinates_vs_evaluation_max_abs
            >= payload["alias_detection_minimum"]
            and np.array_equal(alias.initial_residual, [1.0])
            and np.array_equal(alias.final_residual, [1.0])
        ),
        "bounds_captured": bool(
            bounded.success
            and bounded.rejected_bound_steps == 2
            and [trial.within_bounds for trial in bounded.iteration_captures[0].trials]
            == [False, False, True]
        ),
        "rank_failure_captured": bool(
            not rank_failure.success
            and rank_failure.jacobian_rank == 0
            and np.isinf(rank_failure.jacobian_condition)
        ),
        "immutable_arrays": all(
            record["all_capture_arrays_read_only"] for record in outcomes.values()
        ),
        "ordinary_identity": all(
            outcome.final_residual_vs_evaluation_max_abs
            <= payload["identity_limit"]
            and outcome.final_coordinates_vs_evaluation_max_abs
            <= payload["identity_limit"]
            for outcome in (full_rank, line_failure, bounded, rank_failure)
        ),
        "historical_solver_untouched": _sha(
            ROOT / "src/dynamic_distillation/core_v3/modified_newton_v1.py"
        )
        == payload["implementation_sha256"][
            "src/dynamic_distillation/core_v3/modified_newton_v1.py"
        ],
        "no_live_model_work": True,
    }
    passed = all(bool(value) for value in gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "captured_modified_newton_ready" if passed else "capture_integrity_failed"
        ),
        "decision": (
            "authorize_separately_frozen_live_in_process_failure_capture_contract"
            if passed
            else "stop_captured_solver_path"
        ),
        "outcomes": outcomes,
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "live_property_evaluation_attempted": False,
        "live_column_residual_attempted": False,
        "live_column_jacobian_attempted": False,
        "nonlinear_column_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-137 Captured Modified-Newton Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Full-rank fixture: rank `{full_rank.jacobian_rank}/{dimension}`, residual `{full_rank.final_residual_inf_norm:.3e}`",
                f"- Line-failure trials captured: `{len(line_failure.iteration_captures[0].trials)}`",
                f"- Alias residual/coordinate mismatch: `{alias.final_residual_vs_evaluation_max_abs:.6e}` / `{alias.final_coordinates_vs_evaluation_max_abs:.6e}`",
                f"- Bounded trials rejected before evaluation: `{bounded.rejected_bound_steps}`",
                f"- All capture arrays read-only: `{gates['immutable_arrays']}`",
                "",
                "No live property, column residual/Jacobian, column solve, state advance, timestep, or trajectory was attempted.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
