#!/usr/bin/env python
"""Prepare or execute DD-204's two-root serial/parallel BDF2 equivalence proof."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory as dd202  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_finer_parallel_trajectory as dd193  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_parallel_first_root as dd191  # noqa: E402
from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    component_rate_scales,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    ColoredCentralDifferenceTask,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (  # noqa: E402
    ControlledBDF2History,
    build_controlled_bdf2_history,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_bdf2_residual,
    solve_terminal_inventory_control_bdf2_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2TrajectoryRecord,
    run_terminal_inventory_control_bdf2_trajectory,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_backward_euler_residual,
    solve_terminal_inventory_control_backward_euler_step,
    terminal_inventory_control_step_pattern,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_residual,
)


SCHEMA = "dd204-core-v3-controlled-bdf2-parallel-equivalence-contract-v1"
RESULT_SCHEMA = "dd204-core-v3-controlled-bdf2-parallel-equivalence-result-v1"
DD202_CONTRACT = Path(
    "logs/dd202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_contract_20260814.json"
)
DD202_RESULT = Path(
    "logs/dd202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_20260814.json"
)
DD192_RESULT = Path(
    "logs/dd192_core_v3_terminal_inventory_control_parallel_worker_adjudication_20260813.json"
)
DD203_DOC = Path(
    "docs/dd_203_core_v3_bdf2_production_trajectory_integration_20260814.md"
)
CONTRACT = Path(
    "logs/dd204_core_v3_terminal_inventory_control_bdf2_parallel_equivalence_contract_20260814.json"
)
RESULT = Path(
    "logs/dd204_core_v3_terminal_inventory_control_bdf2_parallel_equivalence_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_204_core_v3_terminal_inventory_control_bdf2_parallel_equivalence_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_204_core_v3_terminal_inventory_control_bdf2_parallel_equivalence_20260814.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_kinematics_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_residual_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_parallel_equivalence.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence.py",
)


_WORKER_CONTEXT: dict[str, Any] | None = None


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


def _state_payload(state: Any) -> dict[str, Any]:
    return {
        "liquid_moles_lbmol": np.asarray(state.liquid_moles_lbmol).tolist(),
        "liquid_mole_fraction": np.asarray(state.liquid_mole_fraction).tolist(),
        "temperature_F": np.asarray(state.temperature_F).tolist(),
        "vapor_mole_fraction": np.asarray(state.vapor_mole_fraction).tolist(),
        "hydraulic_liquid_flow_lbmolph": np.asarray(
            state.hydraulic_liquid_flow_lbmolph
        ).tolist(),
        "vapor_flow_lbmolph": np.asarray(state.vapor_flow_lbmolph).tolist(),
        "distillate_lbmolph": float(state.distillate_lbmolph),
        "bottoms_lbmolph": float(state.bottoms_lbmolph),
        "bubble_vapor_mole_fraction": np.asarray(
            state.bubble_vapor_mole_fraction
        ).tolist(),
        "condenser_duty_BTUph": float(state.condenser_duty_BTUph),
    }


def _history_payload(history: ControlledBDF2History) -> dict[str, Any]:
    return {
        "step_seconds": float(history.step_seconds),
        "current_inventory_lbmol": history.current_inventory_lbmol.tolist(),
        "prior_inventory_lbmol": history.prior_inventory_lbmol.tolist(),
        "current_internal_energy_BTU": history.current_internal_energy_BTU.tolist(),
        "prior_internal_energy_BTU": history.prior_internal_energy_BTU.tolist(),
        "current_controller_memory": history.current_controller_memory.tolist(),
        "prior_controller_memory": history.prior_controller_memory.tolist(),
    }


def _history_from_payload(payload: Mapping[str, Any]) -> ControlledBDF2History:
    return build_controlled_bdf2_history(**payload)


def _worker_initialize(contract_path: str) -> None:
    global _WORKER_CONTEXT
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    (
        spec,
        reference,
        _state,
        controlled,
        provider,
        audit,
        _inventory,
        _memory,
        _initial,
        setpoints,
        product_reference,
    ) = dd191._context(payload)
    _WORKER_CONTEXT = {
        "spec": spec,
        "reference": reference,
        "controlled": controlled,
        "provider": provider,
        "audit": audit,
        "setpoints": setpoints,
        "product_reference": product_reference,
        "fixed_scales": payload["fixed_steady_residual_scales"],
        "root_epoch": None,
    }


def _worker_ping(delay_seconds: float) -> int:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-204 worker context was not initialized")
    time.sleep(float(delay_seconds))
    return int(os.getpid())


def _worker_evaluate(work: Mapping[str, Any]) -> dict[str, Any]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-204 worker context was not initialized")
    context = _WORKER_CONTEXT
    task: ColoredCentralDifferenceTask = work["task"]
    method = str(work["method"])
    root_epoch = str(work["root_epoch"])
    provider = context["provider"]
    audit: ProviderCallAudit = context["audit"]
    before_records = audit.record_count
    before_memo = provider.get_exact_state_memoization_stats()
    basis_rebuilt = context["root_epoch"] != root_epoch
    if basis_rebuilt:
        template = dd202.base.dd187.dd186.dd171._state(work["template_state"])
        context.update(
            {
                "root_epoch": root_epoch,
                "method": method,
                "template": template,
            }
        )
        if method == "backward_euler":
            previous = np.asarray(work["previous_inventory_lbmol"], dtype=float)
            memory = np.asarray(work["previous_controller_memory"], dtype=float)
            initial = np.asarray(work["initial_solve_coordinates"], dtype=float)
            baseline = evaluate_terminal_inventory_control_residual(
                context["controlled"],
                context["spec"],
                context["reference"],
                template,
                provider,
                audit,
                inventory_lbmol=previous,
                controller_memory=memory,
                level_setpoints=context["setpoints"],
                solve_coordinates=initial,
                storage_gradient_BTU_lbmol=np.zeros_like(previous),
                fixed_steady_scales=context["fixed_scales"],
                product_reference_lbmolph=context["product_reference"],
                state_id=f"{root_epoch}:worker_{os.getpid()}:scale_basis",
                evaluation_kind="residual",
            )
            context.update(
                {
                    "previous": previous,
                    "memory": memory,
                    "previous_storage": governing_storage_vector(
                        context["spec"], baseline.base, previous
                    ),
                    "rate_scales": component_rate_scales(
                        context["controlled"].base, baseline.base
                    ),
                }
            )
        elif method == "bdf2":
            context.update(
                {
                    "history": _history_from_payload(work["history"]),
                    "rate_scales": np.asarray(work["rate_scales_lbmolph"], dtype=float),
                }
            )
        else:
            raise ValueError(f"unsupported DD-204 worker method: {method}")
    elif context["method"] != method:
        raise RuntimeError("DD-204 worker method changed within a root epoch")

    started = time.perf_counter()
    if method == "backward_euler":
        evaluation = evaluate_terminal_inventory_control_backward_euler_residual(
            context["controlled"],
            context["spec"],
            context["reference"],
            context["template"],
            provider,
            audit,
            previous_inventory_lbmol=context["previous"],
            previous_internal_energy_BTU=context["previous_storage"],
            previous_controller_memory=context["memory"],
            level_setpoints=context["setpoints"],
            rate_scales_lbmolph=context["rate_scales"],
            solve_coordinates=np.asarray(task.coordinates, dtype=float),
            step_seconds=float(work["step_seconds"]),
            fixed_steady_scales=context["fixed_scales"],
            product_reference_lbmolph=context["product_reference"],
            state_id=task.state_id,
            evaluation_kind="jacobian",
        )
    else:
        evaluation = evaluate_terminal_inventory_control_bdf2_residual(
            context["controlled"],
            context["spec"],
            context["reference"],
            context["template"],
            provider,
            audit,
            history=context["history"],
            level_setpoints=context["setpoints"],
            rate_scales_lbmolph=context["rate_scales"],
            solve_coordinates=np.asarray(task.coordinates, dtype=float),
            step_seconds=float(work["step_seconds"]),
            fixed_steady_scales=context["fixed_scales"],
            product_reference_lbmolph=context["product_reference"],
            state_id=task.state_id,
            evaluation_kind="jacobian",
        )
    elapsed = time.perf_counter() - started
    after_memo = provider.get_exact_state_memoization_stats()
    report = audit.report_since(before_records)
    return {
        "order": int(task.order),
        "residual": np.asarray(evaluation.scaled, dtype=float).tolist(),
        "process_id": int(os.getpid()),
        "method": method,
        "root_epoch": root_epoch,
        "basis_rebuilt": bool(basis_rebuilt),
        "logical_provider_calls": int(audit.record_count - before_records),
        "memo_hits": int(after_memo["hits"] - before_memo["hits"]),
        "memo_misses": int(after_memo["misses"] - before_memo["misses"]),
        "provider_pass": bool(report["pass"]),
        "fallback_attempted": bool(report["fallback_attempted"]),
        "wall_clock_sec": float(elapsed),
    }


def _endpoint(record: TerminalInventoryControlBDF2TrajectoryRecord) -> dict[str, Any]:
    return dd202.base._endpoint(record)


def _maximum_difference(first: Any, second: Any) -> float:
    return float(
        np.max(
            np.abs(
                np.asarray(first, dtype=float).reshape((-1,))
                - np.asarray(second, dtype=float).reshape((-1,))
            )
        )
    )


def _trajectory_comparison(serial: Any, parallel: Any) -> dict[str, Any]:
    if len(serial.records) != len(parallel.records):
        raise ValueError("DD-204 trajectory record counts differ")
    per_root = []
    for first, second in zip(serial.records, parallel.records, strict=True):
        first_endpoint = _endpoint(first)
        second_endpoint = _endpoint(second)
        outcome_first = first.outcome
        outcome_second = second.outcome
        numeric = {
            "cost": abs(float(outcome_first.cost) - float(outcome_second.cost)),
            "optimality": abs(
                float(outcome_first.optimality) - float(outcome_second.optimality)
            ),
            "initial_coordinates": _maximum_difference(
                outcome_first.initial_coordinates, outcome_second.initial_coordinates
            ),
            "final_coordinates": _maximum_difference(
                outcome_first.final_coordinates, outcome_second.final_coordinates
            ),
            "final_residual": _maximum_difference(
                outcome_first.final_residual, outcome_second.final_residual
            ),
            "returned_jacobian": _maximum_difference(
                outcome_first.final_jacobian, outcome_second.final_jacobian
            ),
            "inventory": _maximum_difference(
                first_endpoint["inventory"], second_endpoint["inventory"]
            ),
            "component_rate": _maximum_difference(
                first_endpoint["component_rate"], second_endpoint["component_rate"]
            ),
            "rate_coordinates": _maximum_difference(
                first_endpoint["rate_coordinates"],
                second_endpoint["rate_coordinates"],
            ),
            "energy_rate": _maximum_difference(
                first_endpoint["energy_rate"], second_endpoint["energy_rate"]
            ),
            "controller_memory": _maximum_difference(
                first_endpoint["memory"], second_endpoint["memory"]
            ),
            "algebraic_coordinates": _maximum_difference(
                first_endpoint["algebraic"], second_endpoint["algebraic"]
            ),
            "levels": _maximum_difference(
                first_endpoint["levels"], second_endpoint["levels"]
            ),
            "products": _maximum_difference(
                first_endpoint["products"], second_endpoint["products"]
            ),
        }
        metadata = {
            "index": first.index == second.index,
            "time": first.time_seconds == second.time_seconds,
            "method": first.method == second.method,
            "success": outcome_first.success == outcome_second.success,
            "status": outcome_first.status == outcome_second.status,
            "message": outcome_first.message == outcome_second.message,
            "nfev": outcome_first.nfev == outcome_second.nfev,
            "njev": outcome_first.njev == outcome_second.njev,
        }
        per_root.append(
            {
                "index": int(first.index),
                "method": str(first.method),
                "metadata": metadata,
                "numeric_differences": numeric,
                "maximum_numeric_difference": max(numeric.values()),
            }
        )
    return {
        "per_root": per_root,
        "all_metadata_equal": all(all(item["metadata"].values()) for item in per_root),
        "maximum_numeric_difference": max(
            item["maximum_numeric_difference"] for item in per_root
        ),
    }


def _matrix_comparison(
    serial: Sequence[Mapping[str, Any]], parallel: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if len(serial) != len(parallel):
        return {
            "serial_count": len(serial),
            "parallel_count": len(parallel),
            "metadata_equal": False,
            "maximum_absolute_difference": float("inf"),
        }
    differences = []
    metadata = []
    for first, second in zip(serial, parallel, strict=True):
        differences.append(_maximum_difference(first["matrix"], second["matrix"]))
        metadata.append(first["method"] == second["method"])
    return {
        "serial_count": len(serial),
        "parallel_count": len(parallel),
        "metadata_equal": all(metadata),
        "per_matrix_maximum_absolute_difference": differences,
        "maximum_absolute_difference": max(differences, default=float("inf")),
    }


def _worker_basis_summary(
    evidence: Sequence[Mapping[str, Any]], worker_count: int
) -> dict[str, Any]:
    roots = sorted({str(item["root_epoch"]) for item in evidence})
    rebuilds = {
        root: int(
            sum(
                int(item["basis_rebuilds"])
                for item in evidence
                if str(item["root_epoch"]) == root
            )
        )
        for root in roots
    }
    return {
        "root_count": len(roots),
        "rebuilds_by_root": rebuilds,
        "pass": bool(roots)
        and all(value == int(worker_count) for value in rebuilds.values()),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    limits = payload["limits"]
    return "\n".join(
        (
            "# DD-204 Controlled BDF2 Serial/Parallel Equivalence Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Live path: one `0.125 s` backward-Euler startup plus one `0.125 s` BDF2 root",
            "- Comparison: in-process serial Jacobians versus one persistent four-worker DWSIM pool",
            f"- Matrix / endpoint limits: `{limits['matrix_absolute']}` / `{limits['endpoint_absolute']}`",
            f"- Required solve speedup excluding startup: `{limits['minimum_speedup']}x`",
            f"- Call / governed-wall ceilings: `{limits['logical_provider_calls']}` / `{limits['wall_clock_sec']} s`",
            "- Retry, alternate step, tuning, fallback, clipping, projection, and longer trajectory: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    comparison = payload["trajectory_comparison"]
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-204 Controlled BDF2 Serial/Parallel Equivalence Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed serial/parallel roots: `{payload['serial']['completed_steps']}` / `{payload['parallel']['completed_steps']}`",
            f"- Matrix maximum difference: `{payload['matrix_comparison']['maximum_absolute_difference']:.6e}`",
            f"- Endpoint maximum difference: `{comparison['maximum_numeric_difference']:.6e}`",
            f"- Serial/parallel trajectory wall: `{performance['serial_trajectory_wall_sec']:.6f}` / `{performance['parallel_trajectory_wall_sec']:.6f} s`",
            f"- Solve speedup excluding startup: `{performance['solve_speedup']:.3f}x`",
            f"- Adjusted worker startup / governed wall: `{performance['startup_wall_sec_adjusted']:.3f}` / `{performance['total_governed_wall_sec']:.3f} s`",
            f"- Logical provider calls: `{payload['logical_provider_calls']}`",
            "- Retry, tuning, alternate step, or longer trajectory: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT,
    contract_doc_path: Path = CONTRACT_DOC,
) -> dict[str, Any]:
    source = _load(DD202_CONTRACT)
    result = _load(DD202_RESULT)
    parallel = _load(DD192_RESULT)
    if not result["pass_gate"] or result["decision"] != (
        "authorize_controlled_bdf2_integration_milestone"
    ):
        raise RuntimeError("DD-204 requires accepted DD-202")
    if not parallel["pass_gate"] or parallel["decision"] != (
        "authorize_persistent_parallel_controlled_step_path_under_task_participation_policy"
    ):
        raise RuntimeError("DD-204 requires accepted DD-192 task participation")
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
            "campaign_id": "DD-204",
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (
                    DD202_CONTRACT,
                    DD202_RESULT,
                    DD192_RESULT,
                    DD203_DOC,
                    dd191.DD185_CONTRACT,
                )
            },
            "integration": {
                "duration_seconds": 0.25,
                "step_seconds": 0.125,
                "requested_roots": 2,
                "methods": ["backward_euler", "bdf2"],
                "worker_count": 4,
                "color_count": 17,
                "tasks_per_matrix": 34,
                "startup_ping_delay_sec": 0.15,
            },
            "limits": {
                "scaled_residual": 1.0e-8,
                "required_rank": 58,
                "condition": 1.0e8,
                "matrix_absolute": 1.0e-10,
                "endpoint_absolute": 1.0e-12,
                "minimum_speedup": 1.10,
                "logical_provider_calls": 60000,
                "startup_wall_sec": 30.0,
                "wall_clock_sec": 180.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either two-root path fails closure, rank, condition, physicality, conservation, or provider ownership",
                "serial and parallel Jacobian counts, metadata, matrices, solver decisions, or endpoints differ beyond a frozen limit",
                "any actual Jacobian does not use all four workers or rebuild each worker basis exactly once",
                "parallel trajectory excluding startup is not at least ten percent faster",
                "call, startup, or governed-wall ceiling is exceeded",
                "a retry, alternate step, tuning, fallback, clipping, projection, or longer trajectory occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "trajectory_attempted": False,
            "controller_tuning_attempted": False,
            "retry_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-204 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-204 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-204 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-204 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-204 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-204 result exists; rerun prohibited")
    _git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    serial_context = dd191._context(payload)
    parallel_context = dd191._context(payload)
    (
        serial_spec,
        serial_reference,
        serial_state,
        serial_contract,
        serial_provider,
        serial_audit,
        serial_inventory,
        serial_memory,
        serial_coordinates,
        serial_setpoints,
        serial_products,
    ) = serial_context
    (
        parallel_spec,
        parallel_reference,
        parallel_state,
        parallel_contract,
        parallel_provider,
        parallel_audit,
        parallel_inventory,
        parallel_memory,
        parallel_coordinates,
        parallel_setpoints,
        parallel_products,
    ) = parallel_context
    pattern = terminal_inventory_control_step_pattern(serial_contract)
    if not np.array_equal(
        pattern, terminal_inventory_control_step_pattern(parallel_contract)
    ):
        raise RuntimeError("DD-204 serial and parallel patterns differ")
    settings = dd202.base.dd187.dd186._settings(payload)
    integration = payload["integration"]
    limits = payload["limits"]
    serial_matrices: list[dict[str, Any]] = []
    parallel_matrices: list[dict[str, Any]] = []
    worker_evidence: list[dict[str, Any]] = []

    def serial_builder(method: str, root_epoch: str):
        def builder(objective, point, state_id):
            started = time.perf_counter()
            matrix, groups = colored_central_difference_jacobian(
                objective,
                point,
                pattern=pattern,
                step=settings.jacobian_step,
                state_id=state_id,
            )
            if len(groups) != integration["color_count"]:
                raise RuntimeError("DD-204 serial color count changed")
            serial_matrices.append(
                {
                    "method": method,
                    "root_epoch": root_epoch,
                    "state_id": state_id,
                    "matrix": matrix.copy(),
                    "wall_clock_sec": time.perf_counter() - started,
                }
            )
            return matrix

        return builder

    def serial_startup(*args, **kwargs):
        return solve_terminal_inventory_control_backward_euler_step(
            *args,
            **kwargs,
            jacobian_builder=serial_builder("backward_euler", str(kwargs["name"])),
        )

    def serial_bdf2(*args, **kwargs):
        return solve_terminal_inventory_control_bdf2_step(
            *args,
            **kwargs,
            jacobian_builder=serial_builder("bdf2", str(kwargs["name"])),
        )

    spawn = mp.get_context("spawn")
    total_started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(integration["worker_count"]),
        mp_context=spawn,
        initializer=_worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(_worker_ping, integration["startup_ping_delay_sec"])
            for _ in range(int(integration["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(integration["startup_ping_delay_sec"]), 0.0
        )

        serial_started = time.perf_counter()
        serial = run_terminal_inventory_control_bdf2_trajectory(
            serial_contract,
            serial_spec,
            serial_reference,
            serial_state,
            serial_provider,
            serial_audit,
            initial_inventory_lbmol=serial_inventory,
            initial_controller_memory=serial_memory,
            level_setpoints=serial_setpoints,
            initial_solve_coordinates=serial_coordinates,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=serial_products,
            duration_seconds=integration["duration_seconds"],
            step_seconds=integration["step_seconds"],
            settings=settings,
            name="dd204_serial",
            startup_step_solver=serial_startup,
            bdf2_step_solver=serial_bdf2,
        )
        serial_wall = time.perf_counter() - serial_started

        def parallel_builder(
            method: str, root_epoch: str, work_basis: Mapping[str, Any]
        ):
            def builder(_objective, point, state_id):
                tasks, groups = build_colored_central_difference_tasks(
                    point,
                    pattern=pattern,
                    step=settings.jacobian_step,
                    state_id=state_id,
                )
                work = [
                    {
                        "task": task,
                        "method": method,
                        "root_epoch": root_epoch,
                        **work_basis,
                    }
                    for task in tasks
                ]
                started = time.perf_counter()
                raw = list(pool.map(_worker_evaluate, work, chunksize=1))
                matrix = assemble_colored_central_difference_jacobian(
                    tasks,
                    [
                        ColoredCentralDifferenceResult(
                            order=int(item["order"]),
                            residual=tuple(float(value) for value in item["residual"]),
                        )
                        for item in raw
                    ],
                    pattern=pattern,
                    step=settings.jacobian_step,
                )
                parallel_matrices.append(
                    {
                        "method": method,
                        "root_epoch": root_epoch,
                        "state_id": state_id,
                        "matrix": matrix.copy(),
                        "wall_clock_sec": time.perf_counter() - started,
                    }
                )
                worker_evidence.append(
                    {
                        "method": method,
                        "root_epoch": root_epoch,
                        "state_id": state_id,
                        "color_count": len(groups),
                        "task_count": len(raw),
                        "worker_ids": sorted({int(item["process_id"]) for item in raw}),
                        "basis_rebuilds": int(
                            sum(bool(item["basis_rebuilt"]) for item in raw)
                        ),
                        "logical_provider_calls": int(
                            sum(item["logical_provider_calls"] for item in raw)
                        ),
                        "memo_hits": int(sum(item["memo_hits"] for item in raw)),
                        "memo_misses": int(sum(item["memo_misses"] for item in raw)),
                        "provider_pass": all(item["provider_pass"] for item in raw),
                        "fallback_attempted": any(
                            item["fallback_attempted"] for item in raw
                        ),
                    }
                )
                return matrix

            return builder

        def parallel_startup(*args, **kwargs):
            basis = {
                "template_state": _state_payload(args[3]),
                "previous_inventory_lbmol": np.asarray(
                    kwargs["previous_inventory_lbmol"], dtype=float
                ).tolist(),
                "previous_controller_memory": np.asarray(
                    kwargs["previous_controller_memory"], dtype=float
                ).tolist(),
                "initial_solve_coordinates": np.asarray(
                    kwargs["initial_solve_coordinates"], dtype=float
                ).tolist(),
                "step_seconds": float(kwargs["step_seconds"]),
            }
            return solve_terminal_inventory_control_backward_euler_step(
                *args,
                **kwargs,
                jacobian_builder=parallel_builder(
                    "backward_euler", str(kwargs["name"]), basis
                ),
            )

        def parallel_bdf2(*args, **kwargs):
            basis = {
                "template_state": _state_payload(args[3]),
                "history": _history_payload(kwargs["history"]),
                "rate_scales_lbmolph": np.asarray(
                    kwargs["rate_scales_lbmolph"], dtype=float
                ).tolist(),
                "step_seconds": float(kwargs["step_seconds"]),
            }
            return solve_terminal_inventory_control_bdf2_step(
                *args,
                **kwargs,
                jacobian_builder=parallel_builder("bdf2", str(kwargs["name"]), basis),
            )

        parallel_started = time.perf_counter()
        parallel = run_terminal_inventory_control_bdf2_trajectory(
            parallel_contract,
            parallel_spec,
            parallel_reference,
            parallel_state,
            parallel_provider,
            parallel_audit,
            initial_inventory_lbmol=parallel_inventory,
            initial_controller_memory=parallel_memory,
            level_setpoints=parallel_setpoints,
            initial_solve_coordinates=parallel_coordinates,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=parallel_products,
            duration_seconds=integration["duration_seconds"],
            step_seconds=integration["step_seconds"],
            settings=settings,
            name="dd204_parallel",
            startup_step_solver=parallel_startup,
            bdf2_step_solver=parallel_bdf2,
            deadline_monotonic=total_started + float(limits["wall_clock_sec"]),
        )
        parallel_wall = time.perf_counter() - parallel_started
    total_wall = time.perf_counter() - total_started

    source_limits = dd202.base._load(DD202_CONTRACT)["limits"]
    serial_reports = [
        dd202.base._step_report(record, serial_spec, source_limits, 58)
        for record in serial.records
    ]
    parallel_reports = [
        dd202.base._step_report(record, parallel_spec, source_limits, 58)
        for record in parallel.records
    ]
    comparison = _trajectory_comparison(serial, parallel)
    matrix = _matrix_comparison(serial_matrices, parallel_matrices)
    serial_provider_summary = dd202.base.dd187.dd186._provider_summary(serial_audit)
    parallel_provider_summary = dd202.base.dd187.dd186._provider_summary(parallel_audit)
    logical_calls = (
        serial_provider_summary["total_calls"]
        + parallel_provider_summary["total_calls"]
        + sum(item["logical_provider_calls"] for item in worker_evidence)
    )
    performance = {
        "serial_trajectory_wall_sec": float(serial_wall),
        "parallel_trajectory_wall_sec": float(parallel_wall),
        "parallel_ratio": float(parallel_wall / serial_wall),
        "solve_speedup": float(serial_wall / parallel_wall),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_governed_wall_sec": float(total_wall),
    }
    worker_basis = _worker_basis_summary(
        worker_evidence, int(integration["worker_count"])
    )
    root_reports = serial_reports + parallel_reports
    gates = {
        "serial_complete": serial.completed
        and serial.completed_steps == integration["requested_roots"],
        "parallel_complete": parallel.completed
        and parallel.completed_steps == integration["requested_roots"],
        "methods": [record.method for record in serial.records]
        == integration["methods"]
        and [record.method for record in parallel.records] == integration["methods"],
        "roots": len(root_reports) == 4
        and all(all(report["gates"].values()) for report in root_reports)
        and max(report["residual_inf_norm"] for report in root_reports)
        < limits["scaled_residual"]
        and all(
            report["jacobian_rank"] == limits["required_rank"]
            for report in root_reports
        )
        and max(report["jacobian_condition"] for report in root_reports)
        < limits["condition"],
        "matrix_count_and_metadata": matrix["serial_count"] == matrix["parallel_count"]
        and matrix["serial_count"] > 0
        and matrix["metadata_equal"],
        "matrix_equivalence": matrix["maximum_absolute_difference"]
        < limits["matrix_absolute"],
        "decision_and_endpoint_equivalence": comparison["all_metadata_equal"]
        and comparison["maximum_numeric_difference"] < limits["endpoint_absolute"],
        "worker_participation": all(
            len(item["worker_ids"]) == integration["worker_count"]
            for item in worker_evidence
        ),
        "worker_basis": worker_basis["pass"]
        and worker_basis["root_count"] == integration["requested_roots"],
        "provider": serial_provider_summary["pass"]
        and parallel_provider_summary["pass"]
        and all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "provider_calls": logical_calls < limits["logical_provider_calls"],
        "parallel_speed": performance["solve_speedup"] >= limits["minimum_speedup"],
        "startup_wall": startup_adjusted < limits["startup_wall_sec"],
        "wall_clock": total_wall < limits["wall_clock_sec"],
    }
    passed = all(gates.values())

    def path_summary(path: Any, reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "completed": bool(path.completed),
            "completed_steps": int(path.completed_steps),
            "stop_reason": path.stop_reason,
            "methods": [record.method for record in path.records],
            "worst_residual": max(
                (item["residual_inf_norm"] for item in reports), default=float("inf")
            ),
            "worst_condition": max(
                (item["jacobian_condition"] for item in reports),
                default=float("inf"),
            ),
            "minimum_rank": min((item["jacobian_rank"] for item in reports), default=0),
            "reports": list(reports),
        }

    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "controlled_bdf2_parallel_equivalence_passed"
            if passed
            else "controlled_bdf2_parallel_equivalence_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_bdf2_trajectory_path"
            if passed
            else "retain_serial_bdf2_trajectory_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "serial": path_summary(serial, serial_reports),
        "parallel": path_summary(parallel, parallel_reports),
        "trajectory_comparison": comparison,
        "matrix_comparison": matrix,
        "worker_ping_ids_diagnostic": ping_ids,
        "worker_evidence": worker_evidence,
        "worker_basis": worker_basis,
        "provider": {
            "serial": serial_provider_summary,
            "parallel_main": parallel_provider_summary,
        },
        "logical_provider_calls": int(logical_calls),
        "performance": performance,
        "gates": gates,
        "pass_gate": bool(passed),
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_step_attempted": False,
        "controller_tuning_attempted": False,
        "longer_trajectory_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    serial_provider.set_exact_state_memoization(False, clear=True)
    parallel_provider.set_exact_state_memoization(False, clear=True)
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
