#!/usr/bin/env python
"""Prepare or execute DD-144 post-cache-fix captured short trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_captured_modified_newton as dd137
import run_core_v3_modified_newton_short_controlled_trajectory as dd134
from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    solve_captured_modified_newton,
)
import dynamic_distillation.core_v3.controlled_terminal_trajectory_v1 as trajectory_module


SCHEMA = "dd144-core-v3-post-cachefix-captured-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd144-core-v3-post-cachefix-captured-short-trajectory-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD134_RESULT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_20260805.json"
)
DD139_RESULT = Path(
    "logs/dd139_core_v3_dd138_rate_coordinate_adjudication_20260805.json"
)
DD141_RESULT = Path("logs/dd141_core_v3_thermo_provider_cache_resolution_20260805.json")
DD142_DOC = Path("docs/dd_142_exact_state_property_cache_key_correction_20260805.md")
DD143_RESULT = Path("logs/dd143_core_v3_post_cachefix_jacobian_repeatability_20260805.json")
CONTRACT = Path(
    "logs/dd144_core_v3_post_cachefix_captured_short_trajectory_contract_20260805.json"
)
RESULT = Path("logs/dd144_core_v3_post_cachefix_captured_short_trajectory_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_144_core_v3_post_cachefix_captured_short_trajectory_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_144_core_v3_post_cachefix_captured_short_trajectory_20260805.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/captured_modified_newton_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_trajectory_v1.py",
    "tests/test_core_v3_captured_modified_newton_v1.py",
    "tests/test_core_v3_controlled_terminal_trajectory_v1.py",
    "tools/audit_core_v3_captured_modified_newton.py",
    "tools/run_core_v3_modified_newton_short_controlled_trajectory.py",
    "tools/run_core_v3_post_cachefix_captured_short_trajectory.py",
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
    historical = _load(DD134_CONTRACT)
    dd134_result = _load(DD134_RESULT)
    dd139 = _load(DD139_RESULT)
    dd141 = _load(DD141_RESULT)
    dd143 = _load(DD143_RESULT)
    if (
        dd134_result["decision"] != "stop_modified_newton_controlled_trajectory_path"
        or not dd139["pass"]
        or dd141["classification"] != "rounded_property_cache_alias_confirmed"
        or not dd143["pass"]
        or dd143["decision"]
        != "authorize_separately_frozen_captured_trajectory_successor_contract"
    ):
        raise RuntimeError("DD-144 requires the immutable DD-134/DD-139/DD-141/DD-143 decisions")
    payload = {
        key: value
        for key, value in historical.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "implementation_sha256",
            "hard_stops",
            "contract_payload_sha256",
            "live_property_evaluation_attempted",
            "nonlinear_solve_attempted",
            "timestep_attempted",
            "dynamic_integration_attempted",
            "campaign_executed",
        }
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (
                    DD134_CONTRACT,
                    DD134_RESULT,
                    DD139_RESULT,
                    DD141_RESULT,
                    DD142_DOC,
                    DD143_RESULT,
                )
            },
            "source_contract_payload_sha256": historical["contract_payload_sha256"],
            "scientific_contract_changes": [],
            "solver_evidence": "DD-137 captured modified Newton",
            "capture_residual_identity_limit": 0.0,
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-134/DD-139/DD-141/DD-142/DD-143 source or DD-144 implementation hash changes",
                "the DD-134 state, disturbance, 10-second grids, solver settings, bounds, scales, gates, or limits change",
                "either path is incomplete or any inherited DD-134 gate fails",
                "any step omits immutable initial/final residuals, frozen Jacobian, correction, or line-search evidence",
                "captured residual identity is nonzero or any capture array is writeable",
                "a Jacobian rebuild, alternate solver, retry, fallback, clipping, projection, or changed grid occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-144 Frozen Post-Cache-Fix Captured Short-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific contract changes from DD-134: `none`",
                "- Cache: DD-142 exact-state property keys",
                "- Solver: DD-137 immutable captured modified Newton",
                "- Duration/grids: `10 s`, `10 x 1.0 s`, and `20 x 0.5 s`",
                "- Complete per-step Jacobian, residual, correction, and line-search capture: required",
                "- Provider-call limit: `<80000`",
                "- Wall-clock limit: `<180 s`",
                "- Rebuild, alternate solver, retry, fallback, clipping, projection, or grid change: prohibited",
                "",
                "Passing may authorize a separately frozen trajectory extension. Failure stops with replay-complete evidence.",
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
        raise RuntimeError("DD-144 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-144 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-144 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-144 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    captures: dict[str, Any] = {}
    original_solver = trajectory_module.solve_modified_newton
    original_run = dd134.run_controlled_terminal_trajectory
    original_paths = (dd134.CONTRACT, dd134.RESULT, dd134.RESULT_DOC, dd134.RESULT_SCHEMA)

    def captured_run(*args, **kwargs):
        trajectory_module.solve_modified_newton = solve_captured_modified_newton
        try:
            outcome = original_run(*args, **kwargs)
        finally:
            trajectory_module.solve_modified_newton = original_solver
        captures[outcome.name] = [
            {
                "index": step.index,
                "time_seconds": step.time_seconds,
                "capture": dd137._record(step.outcome),
            }
            for step in outcome.steps
        ]
        return outcome

    dd134.CONTRACT = CONTRACT
    dd134.RESULT = RESULT
    dd134.RESULT_DOC = RESULT_DOC
    dd134.RESULT_SCHEMA = RESULT_SCHEMA
    dd134.run_controlled_terminal_trajectory = captured_run
    try:
        result = dd134.execute()
    finally:
        (
            dd134.CONTRACT,
            dd134.RESULT,
            dd134.RESULT_DOC,
            dd134.RESULT_SCHEMA,
        ) = original_paths
        dd134.run_controlled_terminal_trajectory = original_run
        trajectory_module.solve_modified_newton = original_solver

    flat = [item["capture"] for path in captures.values() for item in path]
    capture_gates = {
        "capture_count_matches_completed_steps": len(flat)
        == sum(len(items) for items in result["trajectories"].values()),
        "all_capture_arrays_read_only": all(
            item["all_capture_arrays_read_only"] for item in flat
        ),
        "residual_identity": all(
            item["final_residual_vs_evaluation_max_abs"]
            <= payload["capture_residual_identity_limit"]
            for item in flat
        ),
        "one_frozen_jacobian_per_step": all(
            item["jacobian_evaluations"] == 1
            and isinstance(item["frozen_jacobian"], list)
            and len(item["frozen_jacobian"]) == payload["required_rank"]
            for item in flat
        ),
    }
    result["schema_id"] = RESULT_SCHEMA
    result["captured_trajectory_evidence"] = captures
    result["capture_gates"] = capture_gates
    result["source_dd134_gates"] = dict(result["gates"])
    result["gates"].update(capture_gates)
    result["pass"] = bool(result["pass"] and all(capture_gates.values()))
    result["classification"] = (
        "post_cachefix_captured_short_trajectory_passed"
        if result["pass"]
        else "post_cachefix_captured_short_trajectory_failed"
    )
    result["decision"] = (
        "authorize_separately_frozen_controlled_trajectory_extension_contract"
        if result["pass"]
        else "stop_with_replay_complete_captured_trajectory_evidence"
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    completed = {
        name: len(steps) for name, steps in result["trajectories"].items()
    }
    residuals = [
        step["residual_inf_norm"]
        for steps in result["trajectories"].values()
        for step in steps
    ]
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-144 Post-Cache-Fix Captured Short-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined steps: `{completed.get('coarse', 0)}` / `{completed.get('refined', 0)}`",
                f"- Worst residual: `{max(residuals):.9e}`",
                f"- Capture gates: `{capture_gates}`",
                f"- DWSIM calls: `{result['provider_provenance']['total_calls']}`",
                f"- Wall clock: `{result['wall_clock_sec']:.3f} s`",
                "",
                "The DD-134 scientific contract is unchanged. Complete captured evidence is retained for every attempted step.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    output = prepare() if args.prepare else execute()
    print(
        json.dumps(
            {
                key: output[key]
                for key in output
                if key
                in {
                    "schema_id",
                    "classification",
                    "decision",
                    "contract_payload_sha256",
                    "wall_clock_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
