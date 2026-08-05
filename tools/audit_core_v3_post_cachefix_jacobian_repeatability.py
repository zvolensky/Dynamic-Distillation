#!/usr/bin/env python
"""Prepare, execute, or work for DD-143 post-cache-fix Jacobian proof."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    controlled_terminal_zero_time_variable_names,
)
from dynamic_distillation.core_v3.jacobian_repeatability_audit_v1 import (
    compare_jacobians,
    jacobian_repeatability,
    relative_spectrum_change,
)


SCHEMA = "dd143-core-v3-post-cachefix-jacobian-repeatability-contract-v1"
RESULT_SCHEMA = "dd143-core-v3-post-cachefix-jacobian-repeatability-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD140_CONTRACT = Path(
    "logs/dd140_core_v3_dd138_jacobian_repeatability_contract_20260805.json"
)
DD140_RESULT = Path("logs/dd140_core_v3_dd138_jacobian_repeatability_20260805.json")
DD141_RESULT = Path("logs/dd141_core_v3_thermo_provider_cache_resolution_20260805.json")
DD142_DOC = Path("docs/dd_142_exact_state_property_cache_key_correction_20260805.md")
CONTRACT = Path(
    "logs/dd143_core_v3_post_cachefix_jacobian_repeatability_contract_20260805.json"
)
RESULT = Path("logs/dd143_core_v3_post_cachefix_jacobian_repeatability_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_143_core_v3_post_cachefix_jacobian_repeatability_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_143_core_v3_post_cachefix_jacobian_repeatability_20260805.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/jacobian_repeatability_audit_v1.py",
    "tools/audit_core_v3_post_cachefix_jacobian_repeatability.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
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


def _entry(case: str, step: str) -> dict[str, str]:
    return {"case": case, "step": step}


def prepare() -> dict[str, Any]:
    dd134 = _load(DD134_CONTRACT)
    dd140_contract = _load(DD140_CONTRACT)
    dd140 = _load(DD140_RESULT)
    dd141 = _load(DD141_RESULT)
    if (
        dd140["classification"] != "jacobian_process_or_order_dependent"
        or dd141["classification"] != "rounded_property_cache_alias_confirmed"
        or dd141["decision"] != "authorize_exact_state_property_cache_key_correction"
    ):
        raise RuntimeError("DD-143 requires the immutable DD-140/DD-141 findings")
    forward = [
        _entry("coarse", "h"),
        _entry("coarse", "half_h"),
        _entry("refined", "h"),
        _entry("refined", "half_h"),
    ]
    reverse = [
        _entry("refined", "half_h"),
        _entry("refined", "h"),
        _entry("coarse", "half_h"),
        _entry("coarse", "h"),
    ]
    interleaved = [
        _entry("coarse", "h"),
        _entry("refined", "half_h"),
        _entry("coarse", "half_h"),
        _entry("refined", "h"),
    ]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD134_CONTRACT,
                DD140_CONTRACT,
                DD140_RESULT,
                DD141_RESULT,
                DD142_DOC,
            )
        },
        "failure_cases": dd140_contract["failure_cases"],
        "jacobian_steps": dd140_contract["jacobian_steps"],
        "execution_orders": [forward, reverse, interleaved],
        "fresh_process_count": 3,
        "matrix_count": 12,
        "row_count": 50,
        "column_count": 50,
        "required_rank": 50,
        "step_color_count": int(dd140_contract["step_color_count"]),
        "condition_limit": float(dd140_contract["condition_limit"]),
        "cross_process_max_abs_limit": 1.0e-10,
        "cross_process_relative_frobenius_limit": 1.0e-10,
        "step_relative_frobenius_limit": 1.0e-3,
        "spectrum_relative_change_limit": 0.25,
        "historical_worst_cross_process_relative": max(
            item["max_relative_frobenius_difference"]
            for item in dd140["cross_process_and_order_repeatability"].values()
        ),
        "minimum_historical_improvement_factor": 1.0e6,
        "provider_call_limit": 20000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "classification_rules": {
            "exact_state_cache_fix_jacobian_proof_passed": (
                "all four matrices are cross-process/order repeatable, step stable, full rank, "
                "conditioned, provider compliant, and improve historical spread by at least 1e6"
            ),
            "jacobian_process_dependence_persists": "cross-process/order repeatability still fails",
            "jacobian_step_sensitivity_persists": "repeatability passes but h versus h/2 fails",
            "audit_invalid": "a source, schema, rank, condition, provider, call, or wall gate fails",
        },
        "hard_stops": [
            "a DD-134/DD-140/DD-141/DD-142 source or DD-143 implementation hash changes",
            "any of the 12 complete matrices is omitted or uses other than the frozen 21-color rule",
            "a rank, condition, provider, call, or wall gate fails",
            "a nonlinear solve, correction, state acceptance, timestep, trajectory, retry, fallback, clipping, or projection is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "live_jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    if float(dd134["jacobian_step"]) != float(payload["jacobian_steps"]["h"]):
        raise RuntimeError("DD-143 Jacobian step changed")
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-143 Frozen Post-Cache-Fix Jacobian Repeatability Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Matrices: `12` complete `50 x 50` matrices",
                "- Points/steps: coarse and refined roots at `1e-5` and `5e-6`",
                "- Processes: grouped-forward, grouped-reverse, and interleaved",
                "- Cross-process matrix limits: `1e-10` absolute and relative Frobenius",
                "- Nonlinear solve, correction, state advance, timestep, and trajectory: prohibited",
                "- Provider-call limit: `<20000`",
                "- Wall-clock limit: `<180 s`",
                "",
                "This is a post-fix numerical proof only. It cannot accept a simulation state.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any], *, require_committed: bool) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-143 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-143 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-143 implementation changed: {path}")
    if require_committed:
        _git("ls-files", "--error-unmatch", str(CONTRACT))
        if (ROOT / RESULT).exists():
            raise RuntimeError("DD-143 result already exists")


def _compact_provenance(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "total_calls": int(report["total_calls"]),
        "violations": report["violations"],
        "fallback_attempted": bool(report["fallback_attempted"]),
        "pass": bool(report["pass"]),
    }


def _worker(worker_index: int, output_path: Path) -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload, require_committed=False)
    source = _load(DD134_CONTRACT)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(source)
    contract = dd128._contract(source)
    pattern = controlled_terminal_step_pattern(contract)
    rows = tuple(row.name for row in contract.rows)
    columns = controlled_terminal_zero_time_variable_names(contract)
    moved_setpoints = TerminalLevelSetpoints(**source["moved_level_setpoints"])
    step_common = {
        "component_rate_scale_lbmolph": float(source["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "fixed_steady_scales": source["fixed_steady_residual_scales"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }
    cases = {case["name"]: case for case in payload["failure_cases"]}
    observations: list[dict[str, Any]] = []
    started = time.perf_counter()
    for position, item in enumerate(payload["execution_orders"][worker_index]):
        case = cases[item["case"]]

        def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
            return evaluate_controlled_terminal_backward_euler_residual(
                contract,
                spec,
                reference,
                template,
                provider,
                call_audit,
                previous_inventory_lbmol=case["previous_inventory_lbmol"],
                previous_top_internal_energy_BTU=case["previous_top_internal_energy_BTU"],
                previous_lower_internal_energy_BTU=case["previous_lower_internal_energy_BTU"],
                previous_controller_memory=case["previous_controller_memory"],
                level_setpoints=moved_setpoints,
                solve_coordinates=candidate,
                step_seconds=float(case["step_seconds"]),
                state_id=state_id,
                evaluation_kind="jacobian",
                **step_common,
            ).scaled

        matrix, groups = colored_central_difference_jacobian(
            objective,
            case["initial_coordinates"],
            pattern=pattern,
            step=float(payload["jacobian_steps"][item["step"]]),
            state_id=f"dd143:worker_{worker_index}:{item['case']}:{item['step']}",
        )
        observations.append(
            {
                "position": position,
                "case": item["case"],
                "step": item["step"],
                "matrix": matrix.tolist(),
                "rank": int(np.linalg.matrix_rank(matrix)),
                "condition": float(np.linalg.cond(matrix)),
                "singular_values": np.linalg.svd(matrix, compute_uv=False).tolist(),
                "color_count": len(groups),
            }
        )
    report = {
        "worker_index": worker_index,
        "process_id": os.getpid(),
        "order": payload["execution_orders"][worker_index],
        "row_names": list(rows),
        "variable_names": list(columns),
        "observations": observations,
        "provider_provenance": _compact_provenance(call_audit.report()),
        "wall_clock_sec": float(time.perf_counter() - started),
        "nonlinear_solve_attempted": False,
        "correction_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload, require_committed=True)
    started = time.perf_counter()
    workers: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dd143_") as temporary:
        for index in range(payload["fresh_process_count"]):
            output_path = Path(temporary) / f"worker_{index}.json"
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker-index", str(index), "--worker-out", str(output_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"DD-143 worker {index} failed: {completed.stderr}")
            workers.append(json.loads(output_path.read_text(encoding="utf-8")))

    rows = tuple(workers[0]["row_names"])
    columns = tuple(workers[0]["variable_names"])
    cases = ("coarse", "refined")
    steps = ("h", "half_h")
    cross: dict[str, Any] = {}
    for case in cases:
        for step in steps:
            matrices = [
                next(
                    item["matrix"]
                    for item in worker["observations"]
                    if item["case"] == case and item["step"] == step
                )
                for worker in workers
            ]
            cross[f"{case}:{step}"] = asdict(
                jacobian_repeatability(matrices, rows, columns)
            )
    sensitivity: dict[str, Any] = {}
    for worker in workers:
        for case in cases:
            by_step = {
                item["step"]: item
                for item in worker["observations"]
                if item["case"] == case
            }
            comparison = asdict(
                compare_jacobians(
                    by_step["h"]["matrix"],
                    by_step["half_h"]["matrix"],
                    rows,
                    columns,
                )
            )
            comparison["spectrum_relative_change"] = relative_spectrum_change(
                by_step["h"]["singular_values"],
                by_step["half_h"]["singular_values"],
            )
            sensitivity[f"worker_{worker['worker_index']}:{case}"] = comparison

    all_observations = [item for worker in workers for item in worker["observations"]]
    elapsed = time.perf_counter() - started
    total_calls = sum(worker["provider_provenance"]["total_calls"] for worker in workers)
    worst_cross = max(item["max_relative_frobenius_difference"] for item in cross.values())
    improvement = payload["historical_worst_cross_process_relative"] / max(
        worst_cross, np.finfo(float).tiny
    )
    gates = {
        "fresh_distinct_processes": len({worker["process_id"] for worker in workers}) == 3,
        "orders_preserved": all(
            worker["order"] == payload["execution_orders"][worker["worker_index"]]
            for worker in workers
        ),
        "twelve_complete_matrices": len(all_observations) == payload["matrix_count"]
        and all(np.asarray(item["matrix"]).shape == (50, 50) for item in all_observations),
        "color_count": all(item["color_count"] == payload["step_color_count"] for item in all_observations),
        "rank": all(item["rank"] == payload["required_rank"] for item in all_observations),
        "condition": all(item["condition"] < payload["condition_limit"] for item in all_observations),
        "provider": all(worker["provider_provenance"]["pass"] for worker in workers),
        "calls": total_calls < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_solve_correction_state_advance_or_timestep": all(
            not worker[flag]
            for worker in workers
            for flag in ("nonlinear_solve_attempted", "correction_attempted", "state_advance_attempted", "timestep_attempted")
        ),
    }
    repeatable = all(
        item["max_abs_spread"] <= payload["cross_process_max_abs_limit"]
        and item["max_relative_frobenius_difference"]
        <= payload["cross_process_relative_frobenius_limit"]
        for item in cross.values()
    )
    step_stable = all(
        item["relative_frobenius_difference"] <= payload["step_relative_frobenius_limit"]
        and item["spectrum_relative_change"] <= payload["spectrum_relative_change_limit"]
        for item in sensitivity.values()
    )
    historical_improvement = improvement >= payload["minimum_historical_improvement_factor"]
    valid = all(gates.values())
    if not valid:
        classification = "audit_invalid"
        decision = "stop_pending_post_fix_audit_integrity_review"
    elif not repeatable:
        classification = "jacobian_process_dependence_persists"
        decision = "stop_solver_work_and_isolate_remaining_derivative_state"
    elif not step_stable:
        classification = "jacobian_step_sensitivity_persists"
        decision = "stop_pending_derivative_step_review"
    elif not historical_improvement:
        classification = "jacobian_process_dependence_persists"
        decision = "stop_pending_historical_improvement_review"
    else:
        classification = "exact_state_cache_fix_jacobian_proof_passed"
        decision = "authorize_separately_frozen_captured_trajectory_successor_contract"
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "workers": workers,
        "cross_process_and_order_repeatability": cross,
        "finite_difference_step_sensitivity": sensitivity,
        "cross_process_repeatable": bool(repeatable),
        "finite_difference_step_stable": bool(step_stable),
        "historical_improvement_factor": float(improvement),
        "aggregate_provider_calls": int(total_calls),
        "wall_clock_sec": float(elapsed),
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(valid and repeatable and step_stable and historical_improvement),
        "nonlinear_solve_attempted": False,
        "correction_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "retry_attempted": False,
        "fallback_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    worst_step = max(item["relative_frobenius_difference"] for item in sensitivity.values())
    worst_spectrum = max(item["spectrum_relative_change"] for item in sensitivity.values())
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-143 Post-Cache-Fix Jacobian Repeatability Result",
                "",
                f"- Classification: `{classification}`",
                f"- Decision: `{decision}`",
                f"- Cross-process/order repeatable: `{repeatable}`",
                f"- Finite-difference step stable: `{step_stable}`",
                f"- Worst cross-process relative Frobenius difference: `{worst_cross:.9e}`",
                f"- Historical improvement factor: `{improvement:.9e}`",
                f"- Worst `h` versus `h/2` relative difference: `{worst_step:.9e}`",
                f"- Worst spectrum change: `{worst_spectrum:.9e}`",
                f"- Condition range: `{min(item['condition'] for item in all_observations):.9e}` to `{max(item['condition'] for item in all_observations):.9e}`",
                f"- Aggregate DWSIM calls: `{total_calls}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "",
                "No nonlinear solve, correction, state advance, timestep, or trajectory was attempted.",
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
    mode.add_argument("--worker-index", type=int)
    parser.add_argument("--worker-out", type=Path)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare()
        status = 0
    elif args.execute:
        output = execute()
        status = 0 if output["pass"] else 2
    else:
        if args.worker_out is None:
            raise SystemExit("--worker-out is required with --worker-index")
        output = _worker(args.worker_index, args.worker_out)
        status = 0
    print(json.dumps({key: output[key] for key in output if key in {"schema_id", "classification", "decision", "contract_payload_sha256", "worker_index", "process_id", "wall_clock_sec", "pass"}}, indent=2))
    raise SystemExit(status)
