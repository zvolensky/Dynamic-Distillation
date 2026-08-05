#!/usr/bin/env python
"""Prepare or execute the property-free DD-131 modified-Newton audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
)
from dynamic_distillation.core_v3.modified_newton_v1 import (
    ModifiedNewtonSettings,
    solve_modified_newton,
)


SCHEMA = "dd131-core-v3-modified-newton-efficiency-contract-v1"
RESULT_SCHEMA = "dd131-core-v3-modified-newton-efficiency-result-v1"
DD130_CONTRACT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_contract_20260805.json")
DD130_RESULT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_20260805.json")
CONTRACT = Path("logs/dd131_core_v3_modified_newton_efficiency_contract_20260805.json")
RESULT = Path("logs/dd131_core_v3_modified_newton_efficiency_20260805.json")
CONTRACT_DOC = Path("docs/dd_131_core_v3_modified_newton_efficiency_contract_20260805.md")
RESULT_DOC = Path("docs/dd_131_core_v3_modified_newton_efficiency_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/modified_newton_v1.py",
    "tests/test_core_v3_modified_newton_v1.py",
    "tools/audit_core_v3_modified_newton_efficiency.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
)


@dataclass(frozen=True)
class Evaluation:
    scaled: np.ndarray


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


def _structural(component_names, source):
    contract = dd128._contract({
        **source,
        "source_mapping": {
            **source["source_mapping"],
            "component_names": list(component_names),
        },
    })
    pattern = controlled_terminal_step_pattern(contract)
    return pattern, int(structural_rank(csr_matrix(pattern))), len(greedy_column_groups(pattern))


def prepare() -> dict[str, Any]:
    source = _load(DD130_CONTRACT)
    result = _load(DD130_RESULT)
    false_gates = sorted(key for key, value in result["gates"].items() if not value)
    if (
        result["classification"] != "dd130_failed"
        or false_gates != ["calls"]
        or result["decision"] != "stop_controlled_terminal_dynamic_handoff"
    ):
        raise RuntimeError("DD-131 requires the DD-130 efficiency-only stop")
    pattern, rank, colors = _structural(source["source_mapping"]["component_names"], source)
    settings = ModifiedNewtonSettings(
        residual_tolerance=1.0e-8,
        max_iterations=12,
        line_search_fractions=(1.0, 0.5, 0.25, 0.125),
        armijo_fraction=1.0e-4,
        condition_limit=1.0e8,
    )
    residual_calls = 28
    root_count = 3
    jacobian_equivalent_evaluations = 2 * colors
    maximum_line_search_evaluations = (
        settings.max_iterations * len(settings.line_search_fractions)
    )
    maximum_evaluations_per_root = (
        1 + jacobian_equivalent_evaluations + maximum_line_search_evaluations
    )
    projected_provider_calls = (
        1 + residual_calls + root_count * maximum_evaluations_per_root * residual_calls
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD130_CONTRACT, DD130_RESULT)
        },
        "source_contract_commit": result["contract_commit"],
        "source_false_gates": false_gates,
        "measured_provider_ledger": {
            "total_calls": int(result["provider_provenance"]["total_calls"]),
            "jacobian_calls": 23520,
            "residual_calls": 644,
            "preparation_calls": 1,
            "calls_per_complete_residual": residual_calls,
            "coarse_jacobian_builds": int(result["outcomes"]["coarse"]["njev"]),
            "half1_jacobian_builds": int(result["outcomes"]["half1"]["njev"]),
            "half2_jacobian_builds": int(result["outcomes"]["half2"]["njev"]),
        },
        "algorithm": {
            **asdict(settings),
            "jacobian_builds_per_root": 1,
            "factorizations_per_root": 1,
            "jacobian_rebuild_or_fallback": False,
            "bound_handling": "reject trial without evaluation; never clip or project",
            "acceptance_norm": "scaled residual infinity norm",
        },
        "three_component_shape": list(pattern.shape),
        "three_component_rank": rank,
        "three_component_color_count": colors,
        "generic_two_component_expected_shape": [40, 40],
        "root_count": root_count,
        "jacobian_equivalent_evaluations_per_root": jacobian_equivalent_evaluations,
        "maximum_line_search_evaluations_per_root": maximum_line_search_evaluations,
        "maximum_equivalent_evaluations_per_root": maximum_evaluations_per_root,
        "projected_provider_call_ceiling": projected_provider_calls,
        "required_projected_provider_call_ceiling": 8000,
        "live_successor_provider_call_limit": 8000,
        "live_successor_requirements": [
            "reuse the exact DD-130 state, disturbance, grids, physical equations, scales, bounds, and endpoint comparison limits",
            "use exactly one 1e-5 colored Jacobian and one LU factorization per root",
            "permit at most 12 corrections and four fixed line-search fractions per root",
            "perform no Jacobian rebuild, alternate solver, clipping, projection, or fallback",
            "reproduce the saved DD-130 coarse, half1, and half2 physical endpoints within 1e-7 normalized",
            "retain all DD-130 residual, direction, refinement, physical, conservation, and provider gates",
            "stop on any scientific gate or 8000-call efficiency failure",
        ],
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "DD-130 evidence or any implementation hash changes",
            "the property-free structure is not square and full rank for three and two components",
            "the worst-case provider-call arithmetic exceeds 8000",
            "the algorithm permits a Jacobian rebuild, clipping, projection, fallback, or changed physics",
            "any live property, residual, nonlinear column solve, timestep, or trajectory occurs in DD-131",
        ],
        "live_property_evaluation_attempted": False,
        "column_residual_evaluation_attempted": False,
        "column_nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text("\n".join((
        "# DD-131 Frozen Modified-Newton Efficiency Contract", "",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        f"- Controlled step structure: `{pattern.shape[0]} x {pattern.shape[1]}`, rank `{rank}`",
        f"- Colored Jacobian groups: `{colors}`",
        "- Jacobians/factorizations per root: `1 / 1`",
        f"- Worst-case projected DWSIM calls: `{projected_provider_calls}`",
        "- DD-131 live DWSIM calls: `0`",
        "- Clipping, projection, rebuild, or fallback: `False`", "",
        "One property-free execution is permitted after this contract is committed.", "",
    )), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-131 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-131 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-131 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-131 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD130_CONTRACT)
    pattern3, rank3, colors3 = _structural(source["source_mapping"]["component_names"], source)
    pattern2, rank2, colors2 = _structural(("water", "methanol"), source)
    settings = ModifiedNewtonSettings(**{
        key: payload["algorithm"][key]
        for key in (
            "residual_tolerance", "max_iterations", "line_search_fractions",
            "armijo_fraction", "condition_limit",
        )
    })
    matrix = np.asarray(((4.0, 1.0), (1.0, 3.0)))
    target = np.asarray((1.0, 2.0))
    linear = solve_modified_newton(
        lambda point, _state_id: Evaluation(matrix @ point - target),
        lambda _point, _state_id: matrix,
        np.zeros(2), settings, name="dd131:linear",
    )
    nonlinear = solve_modified_newton(
        lambda point, _state_id: Evaluation(np.asarray((point[0] + 0.05 * point[0] ** 2 - 1.0,))),
        lambda point, _state_id: np.asarray(((1.0 + 0.1 * point[0],),)),
        (0.0,), settings, name="dd131:nonlinear",
    )
    ledger = payload["measured_provider_ledger"]
    ledger_exact = (
        ledger["jacobian_calls"] + ledger["residual_calls"] + ledger["preparation_calls"]
        == ledger["total_calls"]
        and ledger["coarse_jacobian_builds"]
        + ledger["half1_jacobian_builds"]
        + ledger["half2_jacobian_builds"]
        == 19
    )
    gates = {
        "source_efficiency_only_stop": payload["source_false_gates"] == ["calls"],
        "measured_ledger_exact": ledger_exact,
        "three_component_structure": pattern3.shape == (50, 50) and rank3 == 50 and colors3 == 21,
        "two_component_structure": pattern2.shape == (40, 40) and rank2 == 40 and colors2 > 0,
        "linear_fixture": linear.success and linear.jacobian_evaluations == 1,
        "nonlinear_fixture": nonlinear.success and nonlinear.jacobian_evaluations == 1 and nonlinear.iterations > 1,
        "single_factorization_design": payload["algorithm"]["jacobian_builds_per_root"] == 1 and payload["algorithm"]["factorizations_per_root"] == 1,
        "no_rebuild_or_fallback": not payload["algorithm"]["jacobian_rebuild_or_fallback"],
        "projected_call_ceiling": payload["projected_provider_call_ceiling"] < payload["required_projected_provider_call_ceiling"],
        "no_live_column_work": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd131_passed" if passed else "dd131_failed",
        "decision": "authorize_frozen_modified_newton_live_efficiency_contract" if passed else "stop_modified_newton_path",
        "three_component": {"shape": list(pattern3.shape), "rank": rank3, "colors": colors3},
        "two_component": {"shape": list(pattern2.shape), "rank": rank2, "colors": colors2},
        "linear_fixture": asdict(linear) | {"final_evaluation": None, "jacobian": None, "initial_coordinates": linear.initial_coordinates.tolist(), "final_coordinates": linear.final_coordinates.tolist()},
        "nonlinear_fixture": asdict(nonlinear) | {"final_evaluation": None, "jacobian": None, "initial_coordinates": nonlinear.initial_coordinates.tolist(), "final_coordinates": nonlinear.final_coordinates.tolist()},
        "measured_provider_ledger": ledger,
        "projected_provider_call_ceiling": payload["projected_provider_call_ceiling"],
        "gates": gates,
        "pass": passed,
        "live_provider_calls": 0,
        "column_residual_evaluations": 0,
        "column_nonlinear_solves": 0,
        "timesteps": 0,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text("\n".join((
        "# DD-131 Modified-Newton Efficiency Audit", "",
        f"- Classification: `{result['classification']}`",
        f"- Decision: `{result['decision']}`",
        f"- Three-component structure: `{pattern3.shape[0]} x {pattern3.shape[1]}`, rank `{rank3}`, colors `{colors3}`",
        f"- Two-component structure: `{pattern2.shape[0]} x {pattern2.shape[1]}`, rank `{rank2}`, colors `{colors2}`",
        f"- Worst-case projected DWSIM calls: `{payload['projected_provider_call_ceiling']}`",
        "- Live DWSIM calls: `0`",
        "- Column solve, timestep, or trajectory: `False`", "",
        "Passing authorizes only a separately frozen live efficiency proof against the saved DD-130 endpoints.", "",
    )), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    output = prepare() if args.mode == "prepare" else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.mode == "prepare" or output["pass"] else 2)


if __name__ == "__main__":
    main()
