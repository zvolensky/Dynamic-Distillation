#!/usr/bin/env python
"""Prepare, execute, or work for the frozen DD-136 residual replay audit."""

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
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
)
from dynamic_distillation.core_v3.residual_replay_audit_v1 import (
    residual_replay_spread,
)


SCHEMA = "dd136-core-v3-dd134-residual-replay-contract-v1"
RESULT_SCHEMA = "dd136-core-v3-dd134-residual-replay-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD134_RESULT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_20260805.json"
)
DD135_CONTRACT = Path("logs/dd135_core_v3_dd134_globalization_audit_contract_20260805.json")
DD135_RESULT = Path("logs/dd135_core_v3_dd134_globalization_audit_20260805.json")
CONTRACT = Path("logs/dd136_core_v3_dd134_residual_replay_contract_20260805.json")
RESULT = Path("logs/dd136_core_v3_dd134_residual_replay_20260805.json")
CONTRACT_DOC = Path("docs/dd_136_core_v3_dd134_residual_replay_contract_20260805.md")
RESULT_DOC = Path("docs/dd_136_core_v3_dd134_residual_replay_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/residual_replay_audit_v1.py",
    "tests/test_core_v3_residual_replay_audit_v1.py",
    "tools/audit_core_v3_dd134_residual_replay.py",
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


def prepare() -> dict[str, Any]:
    dd135_contract = _load(DD135_CONTRACT)
    dd135_result = _load(DD135_RESULT)
    if (
        dd135_result["classification"] != "audit_invalid"
        or dd135_result["decision"] != "stop_pending_audit_integrity_review"
        or dd135_result["gates"]["saved_residual_reproduced"]
        or dd135_result["gates"]["stale_failure_reproduced"]
    ):
        raise RuntimeError("DD-136 requires the immutable DD-135 replay-integrity stop")
    reconstructed = {
        name: float(case["reproduced_stalled_residual_inf_norm"])
        for name, case in dd135_result["cases"].items()
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD134_CONTRACT,
                DD134_RESULT,
                DD135_CONTRACT,
                DD135_RESULT,
            )
        },
        "source_classification": dd135_result["classification"],
        "failure_cases": dd135_contract["failure_cases"],
        "dd135_reconstructed_residual_inf_norm": reconstructed,
        "execution_orders": [
            ["coarse", "coarse", "refined", "refined", "coarse", "refined"],
            ["refined", "refined", "coarse", "coarse", "refined", "coarse"],
            ["coarse", "refined", "coarse", "refined", "coarse", "refined"],
        ],
        "fresh_process_count": 3,
        "repetitions_per_case_per_process": 3,
        "row_count": 50,
        "within_process_vector_spread_limit": 1.0e-12,
        "cross_process_and_order_vector_spread_limit": 1.0e-10,
        "dd135_norm_reproduction_absolute_limit": 1.0e-10,
        "dd134_gap_significance_absolute": 1.0e-10,
        "provider_call_limit": 1000,
        "wall_clock_limit_sec": 180.0,
        "classification_rules": {
            "deterministic_replay_dd134_artifact_incomplete": (
                "within-process and cross-process/order residual vectors pass, all norms "
                "reproduce DD-135, and every DD-134 saved-norm gap remains significant"
            ),
            "same_process_residual_nonrepeatability": (
                "at least one repeated same-process residual vector exceeds its limit"
            ),
            "fresh_process_or_call_order_dependence": (
                "same-process repetition passes but cross-process/order or DD-135 replay fails"
            ),
            "dd134_saved_norm_recovered": (
                "repeatability passes and a DD-134 saved-norm gap is no longer significant"
            ),
            "audit_invalid": "a source, observation, schema, provider, call, or wall gate fails",
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-134/DD-135 source or DD-136 implementation hash changes",
            "a worker does not run in its own process and exact precommitted order",
            "any case lacks three complete 50-row residual vectors per process",
            "a provider ownership, call, or wall gate fails",
            "a Jacobian, nonlinear solve, state advance, timestep, trajectory, retry, fallback, clipping, or projection is attempted",
            "an order, repetition count, tolerance, residual equation, scale, bound, provider, or saved state changes",
        ],
        "live_property_evaluation_attempted": False,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
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
                "# DD-136 Frozen DD-134 Residual-Replay Audit Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Saved points: DD-134 coarse `t=7 s` and refined `t=3 s` failures",
                "- Fresh processes: `3`",
                "- Repetitions: `3` complete 50-row residuals per point per process",
                "- Orders: grouped forward, grouped reverse, and interleaved",
                "- Same-process spread limit: `1e-12`",
                "- Cross-process/order spread limit: `1e-10`",
                "- Jacobian, solve, state advance, timestep, and trajectory: prohibited",
                "- Provider-call limit: `<1000`",
                "- Wall-clock limit: `<180 s`",
                "",
                "The audit determines whether DD-135 failed because of provider/residual nonrepeatability or because DD-134 did not serialize a replay-complete numerical failure artifact.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify_payload(payload: dict[str, Any], *, require_committed: bool) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-136 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-136 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-136 implementation changed: {path}")
    if require_committed:
        _git("ls-files", "--error-unmatch", str(CONTRACT))
        if (ROOT / RESULT).exists():
            raise RuntimeError("DD-136 result already exists")


def _worker(worker_index: int, output_path: Path) -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify_payload(payload, require_committed=False)
    source = _load(DD134_CONTRACT)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(source)
    contract = dd128._contract(source)
    moved_setpoints = TerminalLevelSetpoints(**source["moved_level_setpoints"])
    step_common = {
        "component_rate_scale_lbmolph": float(source["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "fixed_steady_scales": source["fixed_steady_residual_scales"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }
    cases = {case["name"]: case for case in payload["failure_cases"]}
    order = payload["execution_orders"][int(worker_index)]
    observations: list[dict[str, Any]] = []
    started = time.perf_counter()
    counts = {name: 0 for name in cases}
    for position, name in enumerate(order):
        case = cases[name]
        counts[name] += 1
        evaluation = evaluate_controlled_terminal_backward_euler_residual(
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
            solve_coordinates=case["stalled_coordinates"],
            step_seconds=float(case["step_seconds"]),
            state_id=f"dd136:worker_{worker_index}:{name}:{counts[name]}",
            evaluation_kind="residual",
            **step_common,
        )
        scaled = np.asarray(evaluation.scaled, dtype=float)
        observations.append(
            {
                "position": int(position),
                "case": name,
                "occurrence": counts[name],
                "scaled_residual": scaled.tolist(),
                "residual_inf_norm": float(np.max(np.abs(scaled))),
                "row_names": list(evaluation.row_names),
            }
        )
    report = {
        "worker_index": int(worker_index),
        "process_id": int(os.getpid()),
        "order": order,
        "observations": observations,
        "provider_provenance": call_audit.report(),
        "wall_clock_sec": float(time.perf_counter() - started),
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _spread_record(samples, row_names) -> dict[str, Any]:
    return asdict(residual_replay_spread(samples, row_names))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify_payload(payload, require_committed=True)
    started = time.perf_counter()
    workers: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dd136_") as temporary:
        temporary_path = Path(temporary)
        for index in range(payload["fresh_process_count"]):
            output_path = temporary_path / f"worker_{index}.json"
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
                raise RuntimeError(
                    f"DD-136 worker {index} failed: {completed.stderr}"
                )
            workers.append(json.loads(output_path.read_text(encoding="utf-8")))

    cases = tuple(case["name"] for case in payload["failure_cases"])
    canonical_rows = tuple(workers[0]["observations"][0]["row_names"])
    within: dict[str, Any] = {}
    cross: dict[str, Any] = {}
    norm_replay: dict[str, Any] = {}
    dd134_gaps: dict[str, Any] = {}
    for worker in workers:
        for name in cases:
            samples = [
                item["scaled_residual"]
                for item in worker["observations"]
                if item["case"] == name
            ]
            within[f"worker_{worker['worker_index']}:{name}"] = _spread_record(
                samples, canonical_rows
            )
    for name in cases:
        observations = [
            item
            for worker in workers
            for item in worker["observations"]
            if item["case"] == name
        ]
        cross[name] = _spread_record(
            [item["scaled_residual"] for item in observations], canonical_rows
        )
        expected_dd135 = float(payload["dd135_reconstructed_residual_inf_norm"][name])
        norms = np.asarray([item["residual_inf_norm"] for item in observations])
        norm_replay[name] = {
            "expected_dd135": expected_dd135,
            "minimum": float(np.min(norms)),
            "maximum": float(np.max(norms)),
            "max_absolute_difference": float(np.max(np.abs(norms - expected_dd135))),
        }
        source_case = next(case for case in payload["failure_cases"] if case["name"] == name)
        saved_dd134 = float(source_case["saved_failure"]["residual_inf_norm"])
        dd134_gaps[name] = {
            "saved_dd134": saved_dd134,
            "replayed_minimum_absolute_gap": float(np.min(np.abs(norms - saved_dd134))),
            "replayed_maximum_absolute_gap": float(np.max(np.abs(norms - saved_dd134))),
        }

    elapsed = time.perf_counter() - started
    total_calls = int(
        sum(worker["provider_provenance"]["total_calls"] for worker in workers)
    )
    observation_complete = all(
        len(worker["observations"])
        == len(cases) * payload["repetitions_per_case_per_process"]
        and all(
            sum(item["case"] == name for item in worker["observations"])
            == payload["repetitions_per_case_per_process"]
            for name in cases
        )
        for worker in workers
    )
    row_schema = all(
        len(item["scaled_residual"]) == payload["row_count"]
        and tuple(item["row_names"]) == canonical_rows
        for worker in workers
        for item in worker["observations"]
    )
    integrity_gates = {
        "fresh_distinct_processes": len({worker["process_id"] for worker in workers})
        == payload["fresh_process_count"],
        "orders_preserved": all(
            worker["order"] == payload["execution_orders"][worker["worker_index"]]
            for worker in workers
        ),
        "observations_complete": observation_complete,
        "row_schema_preserved": row_schema and len(canonical_rows) == payload["row_count"],
        "provider": all(worker["provider_provenance"]["pass"] for worker in workers),
        "calls": total_calls < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_jacobian_solve_state_advance_timestep_or_retry": all(
            not worker[flag]
            for worker in workers
            for flag in (
                "jacobian_attempted",
                "nonlinear_solve_attempted",
                "state_advance_attempted",
                "timestep_attempted",
            )
        ),
    }
    audit_valid = all(bool(value) for value in integrity_gates.values())
    same_process_repeatable = all(
        item["max_abs_spread"] <= payload["within_process_vector_spread_limit"]
        for item in within.values()
    )
    cross_process_repeatable = all(
        item["max_abs_spread"]
        <= payload["cross_process_and_order_vector_spread_limit"]
        for item in cross.values()
    )
    dd135_reproduced = all(
        item["max_absolute_difference"]
        <= payload["dd135_norm_reproduction_absolute_limit"]
        for item in norm_replay.values()
    )
    dd134_gap_persists = all(
        item["replayed_minimum_absolute_gap"]
        > payload["dd134_gap_significance_absolute"]
        for item in dd134_gaps.values()
    )
    if not audit_valid:
        classification = "audit_invalid"
        decision = "stop_pending_replay_audit_integrity_review"
    elif not same_process_repeatable:
        classification = "same_process_residual_nonrepeatability"
        decision = "stop_solver_work_and_audit_provider_repeatability"
    elif not cross_process_repeatable or not dd135_reproduced:
        classification = "fresh_process_or_call_order_dependence"
        decision = "stop_solver_work_and_isolate_process_order_state"
    elif dd134_gap_persists:
        classification = "deterministic_replay_dd134_artifact_incomplete"
        decision = "authorize_separately_frozen_in_process_failure_capture_contract"
    else:
        classification = "dd134_saved_norm_recovered"
        decision = "authorize_separately_frozen_globalization_reconstruction_contract"

    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "workers": workers,
        "within_process_spread": within,
        "cross_process_and_order_spread": cross,
        "dd135_norm_reproduction": norm_replay,
        "dd134_saved_norm_gap": dd134_gaps,
        "same_process_repeatable": bool(same_process_repeatable),
        "cross_process_and_order_repeatable": bool(cross_process_repeatable),
        "dd135_norms_reproduced": bool(dd135_reproduced),
        "dd134_saved_norm_gap_persists": bool(dd134_gap_persists),
        "aggregate_provider_calls": total_calls,
        "wall_clock_sec": elapsed,
        "gates": {key: bool(value) for key, value in integrity_gates.items()},
        "pass": bool(audit_valid),
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "retry_attempted": False,
        "fallback_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# DD-136 DD-134 Residual-Replay Audit Result",
        "",
        f"- Classification: `{classification}`",
        f"- Decision: `{decision}`",
        f"- Same-process repeatable: `{same_process_repeatable}`",
        f"- Cross-process/order repeatable: `{cross_process_repeatable}`",
        f"- DD-135 norms reproduced: `{dd135_reproduced}`",
        f"- DD-134 saved-norm gap persists: `{dd134_gap_persists}`",
    ]
    for name in cases:
        lines.extend(
            (
                f"- {name} cross-process vector spread: `{cross[name]['max_abs_spread']:.9e}` ({cross[name]['worst_row_name']})",
                f"- {name} replayed norm range: `{norm_replay[name]['minimum']:.9e}` to `{norm_replay[name]['maximum']:.9e}`",
                f"- {name} DD-134 minimum norm gap: `{dd134_gaps[name]['replayed_minimum_absolute_gap']:.9e}`",
            )
        )
    lines.extend(
        (
            f"- Aggregate DWSIM calls: `{total_calls}`",
            f"- Wall clock: `{elapsed:.3f} s`",
            "",
            "No Jacobian, nonlinear solve, state advance, timestep, or trajectory was attempted.",
            "",
        )
    )
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
