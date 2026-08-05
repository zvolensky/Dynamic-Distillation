#!/usr/bin/env python
"""Prepare, execute, or work for the frozen DD-140 Jacobian audit."""

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


SCHEMA = "dd140-core-v3-dd138-jacobian-repeatability-contract-v1"
RESULT_SCHEMA = "dd140-core-v3-dd138-jacobian-repeatability-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD135_CONTRACT = Path("logs/dd135_core_v3_dd134_globalization_audit_contract_20260805.json")
DD136_RESULT = Path("logs/dd136_core_v3_dd134_residual_replay_20260805.json")
DD138_CONTRACT = Path(
    "logs/dd138_core_v3_captured_failed_root_reconstruction_contract_20260805.json"
)
DD138_RESULT = Path("logs/dd138_core_v3_captured_failed_root_reconstruction_20260805.json")
DD139_CONTRACT = Path(
    "logs/dd139_core_v3_dd138_rate_coordinate_adjudication_contract_20260805.json"
)
DD139_RESULT = Path(
    "logs/dd139_core_v3_dd138_rate_coordinate_adjudication_20260805.json"
)
CONTRACT = Path("logs/dd140_core_v3_dd138_jacobian_repeatability_contract_20260805.json")
RESULT = Path("logs/dd140_core_v3_dd138_jacobian_repeatability_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_140_core_v3_dd138_jacobian_repeatability_contract_20260805.md"
)
RESULT_DOC = Path("docs/dd_140_core_v3_dd138_jacobian_repeatability_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/jacobian_repeatability_audit_v1.py",
    "tests/test_core_v3_jacobian_repeatability_audit_v1.py",
    "tools/audit_core_v3_dd138_jacobian_repeatability.py",
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
    source = _load(DD134_CONTRACT)
    dd138_contract = _load(DD138_CONTRACT)
    dd139 = _load(DD139_RESULT)
    if (
        not dd139["pass"]
        or dd139["classification"]
        != "dd138_rate_coordinate_adjudication_passed"
        or dd139["decision"]
        != "authorize_frozen_jacobian_repeatability_audit_contract"
    ):
        raise RuntimeError("DD-140 requires the immutable passed DD-139 decision")
    forward = [
        _entry(case, step)
        for case in ("coarse", "refined")
        for step in ("h", "half_h")
        for _ in range(2)
    ]
    reverse = [
        _entry(case, step)
        for case in ("refined", "coarse")
        for step in ("half_h", "h")
        for _ in range(2)
    ]
    interleaved = [
        _entry("coarse", "h"),
        _entry("refined", "half_h"),
        _entry("coarse", "half_h"),
        _entry("refined", "h"),
    ] * 2
    jacobian_step = float(dd138_contract["jacobian_step"])
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD134_CONTRACT,
                DD135_CONTRACT,
                DD136_RESULT,
                DD138_CONTRACT,
                DD138_RESULT,
                DD139_CONTRACT,
                DD139_RESULT,
            )
        },
        "failure_cases": dd138_contract["failure_cases"],
        "jacobian_steps": {"h": jacobian_step, "half_h": jacobian_step / 2.0},
        "execution_orders": [forward, reverse, interleaved],
        "fresh_process_count": 3,
        "repetitions_per_case_step_process": 2,
        "row_count": 50,
        "column_count": 50,
        "required_rank": 50,
        "step_color_count": int(dd138_contract["step_color_count"]),
        "condition_limit": float(dd138_contract["condition_limit"]),
        "repeat_max_abs_limit": 1.0e-10,
        "repeat_relative_frobenius_limit": 1.0e-10,
        "dd138_reproduction_relative_frobenius_limit": 1.0e-10,
        "step_relative_frobenius_limit": 1.0e-3,
        "spectrum_relative_change_limit": 0.25,
        "provider_call_limit": 40000,
        "wall_clock_limit_sec": 180.0,
        "classification_rules": {
            "jacobian_repeatable_and_step_stable": (
                "within-process, cross-process/order, and DD-138 reproduction pass, "
                "and h versus h/2 matrix and spectrum sensitivity pass"
            ),
            "jacobian_repeatable_but_step_sensitive": (
                "repeatability and DD-138 reproduction pass but h versus h/2 sensitivity fails"
            ),
            "jacobian_process_or_order_dependent": (
                "same-point repeated matrices exceed a within-process or cross-process/order limit"
            ),
            "dd138_jacobian_not_reproduced": (
                "fresh h matrices are repeatable but do not reproduce DD-138's captured matrices"
            ),
            "audit_invalid": "a source, schema, rank, condition, provider, call, or wall gate fails",
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-134 through DD-139 source or DD-140 implementation hash changes",
            "a worker does not run in its own process and exact precommitted order",
            "any case/step lacks two complete 50 x 50 matrices per process",
            "a matrix does not use exactly the frozen 21-color central-difference rule",
            "a rank, condition, provider, call, or wall gate fails",
            "a nonlinear solve, correction, state advance, timestep, trajectory, retry, fallback, clipping, or projection is attempted",
            "an order, step, repetition, tolerance, equation, scale, bound, provider, or saved state changes",
        ],
        "live_property_evaluation_attempted": False,
        "live_residual_evaluation_attempted": False,
        "live_jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    if float(source["jacobian_step"]) != jacobian_step:
        raise RuntimeError("DD-134 and DD-138 Jacobian steps differ")
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-140 Frozen DD-138 Jacobian Repeatability Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Points: DD-138 coarse and refined root starts",
                "- Steps: `1e-5` and `5e-6`",
                "- Fresh processes: `3` in grouped-forward, grouped-reverse, and interleaved orders",
                "- Repetitions: `2` complete `50 x 50` matrices per point and step per process",
                "- Jacobian rule: frozen 21-color central difference",
                "- Nonlinear solve, correction, state advance, timestep, and trajectory: prohibited",
                "- Provider-call limit: `<40000`",
                "- Wall-clock limit: `<180 s`",
                "",
                "The audit distinguishes Jacobian repeatability from finite-difference step sensitivity. It cannot accept a simulation state.",
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
        raise RuntimeError("DD-140 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-140 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-140 implementation changed: {path}")
    if require_committed:
        _git("ls-files", "--error-unmatch", str(CONTRACT))
        if (ROOT / RESULT).exists():
            raise RuntimeError("DD-140 result already exists")


def _compact_provenance(report: Mapping[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str], int] = {}
    for record in report["grouped_records"]:
        key = (
            record["quantity"],
            record["provider_interface"],
            record["caller"],
            record["evaluation_kind"],
        )
        grouped[key] = grouped.get(key, 0) + int(record["count"])
    return {
        "total_calls": int(report["total_calls"]),
        "grouped_records_without_state_id": [
            {
                "quantity": key[0],
                "provider_interface": key[1],
                "caller": key[2],
                "evaluation_kind": key[3],
                "count": count,
            }
            for key, count in sorted(grouped.items())
        ],
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
    if pattern.shape != (payload["row_count"], payload["column_count"]):
        raise RuntimeError("DD-140 structure changed")
    row_names = tuple(row.name for row in contract.rows)
    variable_names = controlled_terminal_zero_time_variable_names(contract)
    moved_setpoints = TerminalLevelSetpoints(**source["moved_level_setpoints"])
    step_common = {
        "component_rate_scale_lbmolph": float(source["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "fixed_steady_scales": source["fixed_steady_residual_scales"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }
    cases = {case["name"]: case for case in payload["failure_cases"]}
    order = payload["execution_orders"][worker_index]
    counts: dict[str, int] = {}
    observations: list[dict[str, Any]] = []
    started = time.perf_counter()
    for position, item in enumerate(order):
        name = item["case"]
        step_name = item["step"]
        key = f"{name}:{step_name}"
        counts[key] = counts.get(key, 0) + 1
        case = cases[name]

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
            step=float(payload["jacobian_steps"][step_name]),
            state_id=f"dd140:worker_{worker_index}:{key}:{counts[key]}",
        )
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        observations.append(
            {
                "position": position,
                "case": name,
                "step": step_name,
                "occurrence": counts[key],
                "matrix": matrix.tolist(),
                "rank": int(np.linalg.matrix_rank(matrix)),
                "condition": float(np.linalg.cond(matrix)),
                "singular_values": singular_values.tolist(),
                "color_groups": [list(group) for group in groups],
            }
        )
    provenance = call_audit.report()
    report = {
        "worker_index": worker_index,
        "process_id": os.getpid(),
        "order": order,
        "row_names": list(row_names),
        "variable_names": list(variable_names),
        "observations": observations,
        "provider_provenance": _compact_provenance(provenance),
        "wall_clock_sec": float(time.perf_counter() - started),
        "live_jacobian_evaluation_attempted": True,
        "nonlinear_solve_attempted": False,
        "correction_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _repeatability_record(samples, rows, columns) -> dict[str, Any]:
    return asdict(jacobian_repeatability(samples, rows, columns))


def _comparison_record(left, right, rows, columns) -> dict[str, Any]:
    return asdict(compare_jacobians(left, right, rows, columns))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload, require_committed=True)
    started = time.perf_counter()
    workers: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dd140_") as temporary:
        for index in range(payload["fresh_process_count"]):
            output_path = Path(temporary) / f"worker_{index}.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-index",
                    str(index),
                    "--worker-out",
                    str(output_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"DD-140 worker {index} failed: {completed.stderr}")
            workers.append(json.loads(output_path.read_text(encoding="utf-8")))

    cases = tuple(case["name"] for case in payload["failure_cases"])
    steps = tuple(payload["jacobian_steps"])
    rows = tuple(workers[0]["row_names"])
    columns = tuple(workers[0]["variable_names"])
    within: dict[str, Any] = {}
    cross: dict[str, Any] = {}
    for worker in workers:
        for case in cases:
            for step in steps:
                samples = [
                    item["matrix"]
                    for item in worker["observations"]
                    if item["case"] == case and item["step"] == step
                ]
                within[f"worker_{worker['worker_index']}:{case}:{step}"] = (
                    _repeatability_record(samples, rows, columns)
                )
    for case in cases:
        for step in steps:
            samples = [
                item["matrix"]
                for worker in workers
                for item in worker["observations"]
                if item["case"] == case and item["step"] == step
            ]
            cross[f"{case}:{step}"] = _repeatability_record(samples, rows, columns)

    dd138 = _load(DD138_RESULT)
    reproduction: dict[str, Any] = {}
    for case in cases:
        captured = dd138["outcomes"][case]["frozen_jacobian"]
        comparisons = [
            _comparison_record(captured, item["matrix"], rows, columns)
            for worker in workers
            for item in worker["observations"]
            if item["case"] == case and item["step"] == "h"
        ]
        reproduction[case] = {
            "comparison_count": len(comparisons),
            "max_abs_difference": max(item["max_abs_difference"] for item in comparisons),
            "max_relative_frobenius_difference": max(
                item["relative_frobenius_difference"] for item in comparisons
            ),
            "comparisons": comparisons,
        }

    step_sensitivity: dict[str, Any] = {}
    for worker in workers:
        for case in cases:
            for occurrence in range(1, payload["repetitions_per_case_step_process"] + 1):
                by_step = {
                    item["step"]: item
                    for item in worker["observations"]
                    if item["case"] == case and item["occurrence"] == occurrence
                }
                comparison = _comparison_record(
                    by_step["h"]["matrix"], by_step["half_h"]["matrix"], rows, columns
                )
                comparison["spectrum_relative_change"] = relative_spectrum_change(
                    by_step["h"]["singular_values"],
                    by_step["half_h"]["singular_values"],
                )
                step_sensitivity[
                    f"worker_{worker['worker_index']}:{case}:{occurrence}"
                ] = comparison

    elapsed = time.perf_counter() - started
    all_observations = [item for worker in workers for item in worker["observations"]]
    total_calls = sum(worker["provider_provenance"]["total_calls"] for worker in workers)
    expected_per_worker = len(cases) * len(steps) * payload["repetitions_per_case_step_process"]
    observation_complete = all(
        len(worker["observations"]) == expected_per_worker
        and all(
            sum(
                item["case"] == case and item["step"] == step
                for item in worker["observations"]
            )
            == payload["repetitions_per_case_step_process"]
            for case in cases
            for step in steps
        )
        for worker in workers
    )
    schema_preserved = all(
        np.asarray(item["matrix"]).shape
        == (payload["row_count"], payload["column_count"])
        and len(item["singular_values"]) == payload["row_count"]
        and len(item["color_groups"]) == payload["step_color_count"]
        for item in all_observations
    )
    integrity_gates = {
        "fresh_distinct_processes": len({worker["process_id"] for worker in workers})
        == payload["fresh_process_count"],
        "orders_preserved": all(
            worker["order"] == payload["execution_orders"][worker["worker_index"]]
            for worker in workers
        ),
        "observations_complete": observation_complete,
        "matrix_and_color_schema_preserved": schema_preserved,
        "row_and_variable_names_preserved": all(
            tuple(worker["row_names"]) == rows
            and tuple(worker["variable_names"]) == columns
            for worker in workers
        ),
        "rank": all(item["rank"] == payload["required_rank"] for item in all_observations),
        "condition": all(
            np.isfinite(item["condition"])
            and item["condition"] < payload["condition_limit"]
            for item in all_observations
        ),
        "provider": all(worker["provider_provenance"]["pass"] for worker in workers),
        "calls": total_calls < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_solve_correction_state_advance_or_timestep": all(
            not worker[flag]
            for worker in workers
            for flag in (
                "nonlinear_solve_attempted",
                "correction_attempted",
                "state_advance_attempted",
                "timestep_attempted",
            )
        ),
    }
    repeat_limits = (
        payload["repeat_max_abs_limit"],
        payload["repeat_relative_frobenius_limit"],
    )
    within_repeatable = all(
        item["max_abs_spread"] <= repeat_limits[0]
        and item["max_relative_frobenius_difference"] <= repeat_limits[1]
        for item in within.values()
    )
    cross_repeatable = all(
        item["max_abs_spread"] <= repeat_limits[0]
        and item["max_relative_frobenius_difference"] <= repeat_limits[1]
        for item in cross.values()
    )
    dd138_reproduced = all(
        item["max_relative_frobenius_difference"]
        <= payload["dd138_reproduction_relative_frobenius_limit"]
        for item in reproduction.values()
    )
    step_stable = all(
        item["relative_frobenius_difference"]
        <= payload["step_relative_frobenius_limit"]
        and item["spectrum_relative_change"]
        <= payload["spectrum_relative_change_limit"]
        for item in step_sensitivity.values()
    )
    audit_valid = all(integrity_gates.values())
    if not audit_valid:
        classification = "audit_invalid"
        decision = "stop_pending_jacobian_audit_integrity_review"
    elif not within_repeatable or not cross_repeatable:
        classification = "jacobian_process_or_order_dependent"
        decision = "stop_solver_work_and_isolate_provider_derivative_state"
    elif not dd138_reproduced:
        classification = "dd138_jacobian_not_reproduced"
        decision = "stop_pending_captured_jacobian_provenance_review"
    elif not step_stable:
        classification = "jacobian_repeatable_but_step_sensitive"
        decision = "authorize_separately_frozen_derivative_step_study_contract"
    else:
        classification = "jacobian_repeatable_and_step_stable"
        decision = "authorize_separately_frozen_captured_short_trajectory_contract"

    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "workers": workers,
        "within_process_repeatability": within,
        "cross_process_and_order_repeatability": cross,
        "dd138_captured_jacobian_reproduction": reproduction,
        "finite_difference_step_sensitivity": step_sensitivity,
        "within_process_repeatable": bool(within_repeatable),
        "cross_process_and_order_repeatable": bool(cross_repeatable),
        "dd138_captured_jacobians_reproduced": bool(dd138_reproduced),
        "finite_difference_step_stable": bool(step_stable),
        "aggregate_provider_calls": int(total_calls),
        "wall_clock_sec": float(elapsed),
        "gates": {key: bool(value) for key, value in integrity_gates.items()},
        "pass": bool(audit_valid),
        "live_property_evaluation_attempted": True,
        "live_residual_evaluation_attempted": True,
        "live_jacobian_evaluation_attempted": True,
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
    worst_cross = max(
        item["max_relative_frobenius_difference"] for item in cross.values()
    )
    worst_step = max(
        item["relative_frobenius_difference"] for item in step_sensitivity.values()
    )
    worst_spectrum = max(
        item["spectrum_relative_change"] for item in step_sensitivity.values()
    )
    lines = [
        "# DD-140 DD-138 Jacobian Repeatability Result",
        "",
        f"- Classification: `{classification}`",
        f"- Decision: `{decision}`",
        f"- Within-process repeatable: `{within_repeatable}`",
        f"- Cross-process/order repeatable: `{cross_repeatable}`",
        f"- DD-138 captured matrices reproduced: `{dd138_reproduced}`",
        f"- Finite-difference step stable: `{step_stable}`",
        f"- Worst cross-process relative Frobenius difference: `{worst_cross:.9e}`",
        f"- Worst `h` versus `h/2` relative Frobenius difference: `{worst_step:.9e}`",
        f"- Worst singular-spectrum relative change: `{worst_spectrum:.9e}`",
        f"- Condition range: `{min(item['condition'] for item in all_observations):.9e}` to `{max(item['condition'] for item in all_observations):.9e}`",
        f"- Aggregate DWSIM calls: `{total_calls}`",
        f"- Wall clock: `{elapsed:.3f} s`",
        "",
        "No nonlinear solve, correction, state advance, timestep, or trajectory was attempted.",
        "",
    ]
    (ROOT / RESULT_DOC).write_text("\n".join(lines), encoding="utf-8")
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
                    "worker_index",
                    "process_id",
                    "wall_clock_sec",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(status)
