#!/usr/bin/env python
"""Prepare or execute DD-210's four-versus-eight worker scaling proof."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory as dd202  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_30s_production as dd209  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence as dd204  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_production_backend_replay as dd208  # noqa: E402
from dynamic_distillation.core_v3.persistent_parallel_colored_jacobian_v1 import (  # noqa: E402
    PersistentParallelColoredJacobian,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_parallel_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2ParallelStepSolvers,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 import (  # noqa: E402
    run_terminal_inventory_control_bdf2_trajectory,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    terminal_inventory_control_step_pattern,
)


SCHEMA = "dd210-core-v3-bdf2-worker-scaling-contract-v1"
RESULT_SCHEMA = "dd210-core-v3-bdf2-worker-scaling-result-v1"
DD209_CONTRACT = dd209.CONTRACT
DD209_RESULT = Path(
    "logs/dd209_core_v3_terminal_inventory_control_bdf2_30s_production_20260814.json"
)
DD208_RESULT = dd209.DD208_RESULT
CONTRACT = Path(
    "logs/dd210_core_v3_terminal_inventory_control_bdf2_worker_scaling_contract_20260814.json"
)
RESULT = Path(
    "logs/dd210_core_v3_terminal_inventory_control_bdf2_worker_scaling_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_210_core_v3_terminal_inventory_control_bdf2_worker_scaling_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_210_core_v3_terminal_inventory_control_bdf2_worker_scaling_20260814.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_parallel_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_worker_scaling.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_worker_scaling.py",
)


class RecordingPersistentParallelColoredJacobian(PersistentParallelColoredJacobian):
    """Retain matrices for a bounded equivalence proof."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.matrices: list[dict[str, Any]] = []

    def build(
        self,
        point: Sequence[float],
        state_id: str,
        *,
        method: str,
        root_epoch: str,
        work_basis: Mapping[str, Any],
    ) -> np.ndarray:
        matrix = super().build(
            point,
            state_id,
            method=method,
            root_epoch=root_epoch,
            work_basis=work_basis,
        )
        self.matrices.append(
            {
                "method": str(method),
                "root_epoch": str(root_epoch),
                "state_id": str(state_id),
                "matrix": matrix.copy(),
            }
        )
        return matrix


def _matrix_comparison(
    first: Sequence[Mapping[str, Any]], second: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if len(first) != len(second):
        return {
            "first_count": len(first),
            "second_count": len(second),
            "metadata_equal": False,
            "maximum_absolute_difference": float("inf"),
        }
    metadata_equal = True
    maximum = 0.0
    for left, right in zip(first, second, strict=True):
        metadata_equal = metadata_equal and all(
            left[key] == right[key] for key in ("method", "root_epoch", "state_id")
        )
        maximum = max(
            maximum,
            float(
                np.max(
                    np.abs(
                        np.asarray(left["matrix"], dtype=float)
                        - np.asarray(right["matrix"], dtype=float)
                    )
                )
            ),
        )
    return {
        "first_count": len(first),
        "second_count": len(second),
        "metadata_equal": metadata_equal,
        "maximum_absolute_difference": maximum,
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    limits = payload["limits"]
    return "\n".join(
        (
            "# DD-210 Four-Versus-Eight Worker Scaling Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Each path: one `0.125 s` backward-Euler startup plus one `0.125 s` BDF2 root",
            "- Science and source backend: unchanged from accepted DD-208/DD-209",
            "- Compared worker counts: `4` and `8`",
            f"- Matrix/report absolute limit: `{limits['equivalence_absolute']}`",
            f"- Required warm-trajectory speedup: `{limits['minimum_speedup']}x`",
            f"- Governed wall limit: `{limits['wall_clock_sec']} s`",
            "- Retry, alternate worker count, tuning, fallback, clipping, projection, and longer trajectory: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-210 Four-Versus-Eight Worker Scaling Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Four/eight-worker trajectory wall: `{performance['four_worker_trajectory_wall_sec']:.6f}` / `{performance['eight_worker_trajectory_wall_sec']:.6f} s`",
            f"- Eight-worker speedup: `{performance['eight_worker_speedup']:.3f}x`",
            f"- Matrix/report maximum differences: `{payload['matrix_comparison']['maximum_absolute_difference']:.6e}` / `{payload['report_comparison']['maximum_numeric_difference']:.6e}`",
            f"- Matrix counts: `{payload['four_worker']['matrix_count']}` / `{payload['eight_worker']['matrix_count']}`",
            f"- Logical provider calls / governed wall: `{payload['logical_provider_calls']}` / `{performance['total_governed_wall_sec']:.3f} s`",
            "- Retry, tuning, alternate worker count, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = dd209._load(DD209_CONTRACT)
    accepted = dd209._load(DD209_RESULT)
    backend = dd209._load(DD208_RESULT)
    if not accepted["pass_gate"] or accepted["completed_roots"] != 360:
        raise RuntimeError("DD-210 requires accepted DD-209")
    if not backend["pass_gate"]:
        raise RuntimeError("DD-210 requires accepted DD-208 source backend")
    payload = {
        key: source[key]
        for key in (
            "workbook",
            "workbook_sha256",
            "property_package",
            "source_mapping",
            "operating_spec",
            "reference",
            "accepted_root_state",
            "accepted_root_inventory_lbmol",
            "initial_solve_coordinates",
            "initial_controller_memory",
            "level_setpoints",
            "product_reference_lbmolph",
            "fixed_steady_residual_scales",
            "solver",
            "physical_refinement_limits",
        )
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "result_schema_id": RESULT_SCHEMA,
            "campaign_id": "DD-210",
            "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd209._sha(ROOT / path)
                for path in (DD209_CONTRACT, DD209_RESULT, DD208_RESULT)
            },
            "integration": {
                "duration_seconds": 0.25,
                "step_seconds": 0.125,
                "requested_roots": 2,
                "methods": ["backward_euler", "bdf2"],
                "color_count": 17,
                "tasks_per_matrix": 34,
                "worker_counts": [4, 8],
                "startup_ping_delay_sec": 0.15,
            },
            "root_limits": source["limits"],
            "limits": {
                "equivalence_absolute": 1.0e-12,
                "scaled_residual": 1.0e-8,
                "required_rank": 58,
                "condition": 1.0e8,
                "minimum_speedup": 1.30,
                "logical_provider_calls": 30000,
                "startup_wall_sec": 30.0,
                "wall_clock_sec": 120.0,
            },
            "implementation_sha256": {
                path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either worker-count path fails either root or an inherited root gate",
                "matrix metadata or values differ beyond the frozen absolute limit",
                "serialized root reports differ beyond the frozen absolute limit",
                "any matrix omits a configured worker or any root violates basis lifecycle",
                "provider ownership fails or any fallback occurs",
                "eight-worker warm trajectory speedup is below 1.30x",
                "provider-call, startup, or governed-wall ceiling is exceeded",
                "a retry, alternate worker count, tuning, clipping, projection, fallback, or longer trajectory occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "trajectory_attempted": False,
            "retry_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = dd209._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-210 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd209._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-210 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-210 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-210 implementation changed: {path}")
    if dd209._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-210 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-210 result exists; rerun prohibited")
    dd209._git("ls-files", "--error-unmatch", str(contract_path))


def _run_path(
    payload: Mapping[str, Any],
    contract_path: Path,
    worker_count: int,
    deadline: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    (
        spec,
        reference,
        state,
        controlled,
        provider,
        audit,
        inventory,
        memory,
        coordinates,
        setpoints,
        products,
    ) = dd204.dd191._context(payload)
    settings = dd202.base.dd187.dd186._settings(payload)
    integration = payload["integration"]
    pattern = terminal_inventory_control_step_pattern(controlled)
    spawn = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(worker_count),
        mp_context=spawn,
        initializer=dd204._worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(dd204._worker_ping, integration["startup_ping_delay_sec"])
            for _ in range(int(worker_count))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(integration["startup_ping_delay_sec"]), 0.0
        )
        jacobians = RecordingPersistentParallelColoredJacobian(
            pool,
            dd204._worker_evaluate,
            pattern=pattern,
            step=settings.jacobian_step,
            worker_count=int(worker_count),
        )
        backend = TerminalInventoryControlBDF2ParallelStepSolvers(jacobians)
        trajectory_started = time.perf_counter()
        trajectory = run_terminal_inventory_control_bdf2_trajectory(
            controlled,
            spec,
            reference,
            state,
            provider,
            audit,
            initial_inventory_lbmol=inventory,
            initial_controller_memory=memory,
            level_setpoints=setpoints,
            initial_solve_coordinates=coordinates,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=products,
            duration_seconds=float(integration["duration_seconds"]),
            step_seconds=float(integration["step_seconds"]),
            settings=settings,
            name="dd210_worker_equivalence",
            step_solver_backend=backend,
            deadline_monotonic=deadline,
        )
        trajectory_wall = time.perf_counter() - trajectory_started
        evidence = [asdict(item) for item in jacobians.evidence]
        worker_calls = jacobians.logical_provider_calls
        matrices = list(jacobians.matrices)
    provider_summary = dd202.base.dd187.dd186._provider_summary(audit)
    provider.set_exact_state_memoization(False, clear=True)
    reports = [
        dd202.base._step_report(record, spec, payload["root_limits"], 58)
        for record in trajectory.records
    ]
    summary = {
        "worker_count": int(worker_count),
        "completed": bool(trajectory.completed),
        "completed_steps": int(trajectory.completed_steps),
        "stop_reason": trajectory.stop_reason,
        "methods": [record.method for record in trajectory.records],
        "reports": reports,
        "matrix_count": len(matrices),
        "worker_evidence": evidence,
        "basis": dd209._basis_summary(evidence, int(worker_count)),
        "provider": provider_summary,
        "logical_provider_calls": int(provider_summary["total_calls"] + worker_calls),
        "startup_ping_process_ids": ping_ids,
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "trajectory_wall_sec": float(trajectory_wall),
    }
    return summary, matrices


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = dd209._load(contract_path)
    _verify(payload, contract_path, result_path)
    limits = payload["limits"]
    total_started = time.perf_counter()
    deadline = total_started + float(limits["wall_clock_sec"])
    four, four_matrices = _run_path(payload, contract_path, 4, deadline)
    eight, eight_matrices = _run_path(payload, contract_path, 8, deadline)
    total_wall = time.perf_counter() - total_started

    matrix_comparison = _matrix_comparison(four_matrices, eight_matrices)
    normalized_equal = dd208._normalized(four["reports"]) == dd208._normalized(
        eight["reports"]
    )
    report_difference = dd208._maximum_numeric_difference(
        four["reports"], eight["reports"]
    )
    report_comparison = {
        "serialized_exact": normalized_equal,
        "maximum_numeric_difference": report_difference,
    }
    performance = {
        "four_worker_trajectory_wall_sec": four["trajectory_wall_sec"],
        "eight_worker_trajectory_wall_sec": eight["trajectory_wall_sec"],
        "eight_worker_speedup": float(
            four["trajectory_wall_sec"] / eight["trajectory_wall_sec"]
        ),
        "four_worker_startup_wall_sec_adjusted": four["startup_wall_sec_adjusted"],
        "eight_worker_startup_wall_sec_adjusted": eight["startup_wall_sec_adjusted"],
        "total_governed_wall_sec": float(total_wall),
    }
    logical_calls = int(
        four["logical_provider_calls"] + eight["logical_provider_calls"]
    )

    def path_gates(path: Mapping[str, Any], worker_count: int) -> bool:
        evidence = path["worker_evidence"]
        return (
            path["completed"]
            and path["completed_steps"] == payload["integration"]["requested_roots"]
            and path["methods"] == payload["integration"]["methods"]
            and len(path["reports"]) == 2
            and all(all(report["gates"].values()) for report in path["reports"])
            and path["matrix_count"] > 0
            and all(
                len(item["worker_ids"]) == worker_count
                and item["color_count"] == payload["integration"]["color_count"]
                and item["task_count"] == payload["integration"]["tasks_per_matrix"]
                for item in evidence
            )
            and path["basis"]["pass"]
            and path["basis"]["root_count"] == payload["integration"]["requested_roots"]
            and path["provider"]["pass"]
            and all(item["provider_pass"] for item in evidence)
            and not any(item["fallback_attempted"] for item in evidence)
        )

    gates = {
        "four_worker_path": path_gates(four, 4),
        "eight_worker_path": path_gates(eight, 8),
        "matrix_equivalence": matrix_comparison["metadata_equal"]
        and matrix_comparison["maximum_absolute_difference"]
        < limits["equivalence_absolute"],
        "report_equivalence": normalized_equal
        and report_difference < limits["equivalence_absolute"],
        "speedup": performance["eight_worker_speedup"] >= limits["minimum_speedup"],
        "provider_calls": logical_calls < limits["logical_provider_calls"],
        "startup_wall": max(
            four["startup_wall_sec_adjusted"],
            eight["startup_wall_sec_adjusted"],
        )
        < limits["startup_wall_sec"],
        "wall_clock": total_wall < limits["wall_clock_sec"],
    }
    passed = all(gates.values())

    def persisted(path: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in path.items() if key != "reports"} | {
            "reports": path["reports"]
        }

    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-210",
        "classification": (
            "controlled_bdf2_eight_worker_scaling_passed"
            if passed
            else "controlled_bdf2_eight_worker_scaling_failed"
        ),
        "decision": (
            "adopt_eight_worker_production_jacobian_backend"
            if passed
            else "retain_four_worker_production_jacobian_backend"
        ),
        "contract_commit": dd209._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "four_worker": persisted(four),
        "eight_worker": persisted(eight),
        "matrix_comparison": matrix_comparison,
        "report_comparison": report_comparison,
        "logical_provider_calls": logical_calls,
        "performance": performance,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_worker_count_attempted": False,
        "controller_tuning_attempted": False,
        "fallback_attempted": False,
        "longer_trajectory_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "integration": output["integration"],
                    "campaign_executed": output["campaign_executed"],
                },
                indent=2,
            )
        )
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(
            json.dumps(
                {
                    "classification": output["classification"],
                    "pass_gate": output["pass_gate"],
                    "decision": output["decision"],
                },
                indent=2,
            )
        )
        raise SystemExit(0 if output["pass_gate"] else 2)
