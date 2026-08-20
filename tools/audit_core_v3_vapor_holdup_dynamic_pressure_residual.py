#!/usr/bin/env python
"""Prepare or execute DD-273's live dynamic-pressure residual audit."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_short_trajectory as dd267  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_thirty_second_bound_corrected as dd271  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dynamic_pressure_contract,
    build_vapor_holdup_dynamic_pressure_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_implicit_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_dynamic_pressure_implicit_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_implicit_residual_v1 import (  # noqa: E402
    controlled_implicit_initial_coordinates,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (  # noqa: E402
    vapor_holdup_terminal_control_pattern,
)


SCHEMA = "dd273-core-v3-vapor-holdup-dynamic-pressure-residual-contract-v1"
RESULT_SCHEMA = "dd273-core-v3-vapor-holdup-dynamic-pressure-residual-result-v1"
CONTRACT = Path("logs/dd273_core_v3_vapor_holdup_dynamic_pressure_residual_contract_20260820.json")
RESULT = Path("logs/dd273_core_v3_vapor_holdup_dynamic_pressure_residual_20260820.json")
EVIDENCE = Path("logs/dd273_core_v3_vapor_holdup_dynamic_pressure_residual_20260820.npz")
CONTRACT_DOC = Path("docs/dd_273_core_v3_vapor_holdup_dynamic_pressure_residual_contract_20260820.md")
RESULT_DOC = Path("docs/dd_273_core_v3_vapor_holdup_dynamic_pressure_residual_20260820.md")
SOURCE_RESULT = dd271.RESULT
SOURCE_EVIDENCE = dd271.EVIDENCE
SOURCE_STRUCTURE = Path("logs/dd272_core_v3_vapor_holdup_dynamic_pressure_contract_20260820.json")
IMPLEMENTATION = (
    Path("tools/audit_core_v3_vapor_holdup_dynamic_pressure_residual.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_dynamic_pressure_contract_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_dynamic_pressure_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_terminal_control_implicit_residual_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def prepare() -> dict[str, Any]:
    source = json.loads((ROOT / SOURCE_RESULT).read_text(encoding="utf-8"))
    structure = json.loads((ROOT / SOURCE_STRUCTURE).read_text(encoding="utf-8"))
    if not source.get("pass_gate") or not structure.get("pass_gate"):
        raise RuntimeError("DD-273 requires accepted DD-271 and DD-272 sources")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": "DD-272 authorizes one live fixed-duty residual and Jacobian audit",
        "sources": {
            SOURCE_RESULT.as_posix(): _sha(SOURCE_RESULT),
            SOURCE_EVIDENCE.as_posix(): _sha(SOURCE_EVIDENCE),
            SOURCE_STRUCTURE.as_posix(): _sha(SOURCE_STRUCTURE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "audit": {
            "source_replay_steps": 120,
            "proposed_timestep_sec": 0.25,
            "specified_condenser_duty": "accepted DD-271 endpoint duty",
            "jacobian_steps": [1.0e-5, 5.0e-6],
            "solver_attempted": False,
        },
        "limits": {
            "source_product_parity": 1.0e-10,
            "source_level_parity": 1.0e-10,
            "finite_predictor_residual": 0.1,
            "rank": 262,
            "condition": 1.0e8,
            "spectrum_relative_change": 1.0e-4,
            "matrix_relative_change": 1.0e-4,
            "duty_row_derivative_error": 1.0e-8,
            "logical_provider_calls": 30000,
            "wall_clock_sec": 180.0,
        },
        "hard_stops": [
            "saved DD-271 endpoint cannot be replayed",
            "successor structure is not full rank",
            "residual is nonfinite or exceeds the frozen predictor limit",
            "either Jacobian loses rank or exceeds the conditioning limit",
            "Jacobian spectra or matrices are step-size sensitive",
            "the fixed-duty row lacks its exact local derivative",
            "provider ownership or no-fallback gate fails",
            "a nonlinear solve, timestep, retry, tuning, or fallback occurs",
        ],
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if any((ROOT / path).exists() for path in (CONTRACT, CONTRACT_DOC)):
        raise RuntimeError("DD-273 contract already exists")
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-273 Dynamic-Pressure Residual Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Replay all 120 accepted DD-271 endpoints without solving.",
                "- Fix condenser duty at the accepted endpoint value.",
                "- Evaluate one next-step predictor and Jacobians at `1e-5` and `5e-6`.",
                "- Require rank 262, condition below `1e8`, stable matrices, exact duty-row derivative, and provider ownership.",
                "- Nonlinear solve, accepted timestep, retry, tuning, or fallback: `False`.",
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
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-273 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-273 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-273 implementation changed: {path}")
    if (ROOT / RESULT).exists() or (ROOT / EVIDENCE).exists():
        raise RuntimeError("DD-273 result exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", CONTRACT.as_posix())


def _replay(context: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads((ROOT / SOURCE_RESULT).read_text(encoding="utf-8"))
    evidence = np.load(ROOT / SOURCE_EVIDENCE)
    coordinates = np.asarray(evidence["nominal_coordinates"], dtype=float)
    memories = np.asarray(evidence["nominal_controller_memory"], dtype=float)
    hold = json.loads((ROOT / dd267.SOURCE_HOLD).read_text(encoding="utf-8"))
    memory = np.asarray(hold["terminal"]["controller_memory_previous"], dtype=float)
    reference = context["reference"]
    final = None
    for index in range(120):
        final = dd267._evaluate(
            context,
            reference,
            memory,
            coordinates[index],
            0.25,
            f"dd273:source_replay_{index + 1}",
            "residual",
        )
        if np.max(np.abs(final.controller_memory_endpoint - memories[index])) > 1.0e-12:
            raise RuntimeError("DD-273 controller-memory replay failed")
        reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
    if final is None:
        raise RuntimeError("DD-273 source replay is empty")
    saved = result["nominal_endpoints"][-1]
    parity = {
        "distillate_lbmolph": abs(final.distillate_lbmolph - saved["distillate_lbmolph"]),
        "bottoms_lbmolph": abs(final.bottoms_lbmolph - saved["bottoms_lbmolph"]),
        "level_fraction": float(
            np.max(np.abs(final.level_fraction - np.asarray(saved["level_fraction"])))
        ),
    }
    return {"reference": reference, "memory": memory, "final": final, "parity": parity}


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    return float(
        np.linalg.norm(left - right)
        / max(np.linalg.norm(left), np.linalg.norm(right), 1.0e-30)
    )


def execute() -> dict[str, Any]:
    payload = json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))
    _verify(payload)
    context = dd267._context()
    replay = _replay(context)
    successor = build_vapor_holdup_dynamic_pressure_contract(context["contract"])
    structure = audit_vapor_holdup_dynamic_pressure_contract(successor)
    context = {**context, "contract": successor}
    previous = replay["final"]
    point = controlled_implicit_initial_coordinates(
        successor,
        controller_rates_per_sec=previous.controller_rate_per_sec,
        timestep_sec=0.25,
        previous_coordinates=np.zeros(262),
        product_log_ratios_previous=previous.product_log_ratio,
    )
    specified_duty = float(replay["reference"].condenser_duty_BTUph)

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_vapor_holdup_dynamic_pressure_implicit_residual(
            successor,
            context["geometry"],
            replay["reference"],
            context["balance_inputs"],
            context["spec"].hydraulic_geometry,
            replace(context["numerical"], timestep_sec=0.25),
            context["provider"],
            context["audit"],
            candidate,
            controller_memory_previous=replay["memory"],
            specified_condenser_duty_BTUph=specified_duty,
            state_id=state_id,
            evaluation_kind="residual" if "predictor" in state_id else "jacobian",
        ).scaled

    started = time.perf_counter()
    predictor = objective(point, "dd273:predictor")
    pattern = vapor_holdup_terminal_control_pattern(successor)
    matrices: list[np.ndarray] = []
    steps: list[dict[str, Any]] = []
    for step in payload["audit"]["jacobian_steps"]:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=float(step),
            state_id=f"dd273:jacobian:h={step:.1e}",
        )
        rank, condition, singular = dd249._rank_condition(matrix)
        matrices.append(matrix)
        steps.append(
            {
                "step": step,
                "rank": rank,
                "condition": condition,
                "color_count": len(groups),
                "singular_values": singular.tolist(),
            }
        )
    wall = time.perf_counter() - started
    duty_index = next(
        index
        for index, row in enumerate(successor.base.rows)
        if row.block == "condenser_duty_specification"
    )
    duty_column = next(
        index
        for index, variable in enumerate(
            (*successor.derivative_variables, *successor.algebraic_variables)
        )
        if variable.name == "Q_C"
    )
    spectrum_change = _relative_change(
        np.asarray(steps[0]["singular_values"]),
        np.asarray(steps[1]["singular_values"]),
    )
    matrix_change = _relative_change(matrices[0], matrices[1])
    derivative_error = max(
        abs(float(matrix[duty_index, duty_column]) - 1.0) for matrix in matrices
    )
    limits = payload["limits"]
    provider = context["audit"].report()
    gates = {
        "source_product_parity": max(
            replay["parity"]["distillate_lbmolph"],
            replay["parity"]["bottoms_lbmolph"],
        ) < limits["source_product_parity"],
        "source_level_parity": replay["parity"]["level_fraction"] < limits["source_level_parity"],
        "structure": structure.pass_gate,
        "finite_predictor": bool(
            np.all(np.isfinite(predictor))
            and np.max(np.abs(predictor)) < limits["finite_predictor_residual"]
        ),
        "rank": all(item["rank"] == limits["rank"] for item in steps),
        "condition": all(item["condition"] < limits["condition"] for item in steps),
        "spectrum": spectrum_change < limits["spectrum_relative_change"],
        "matrix": matrix_change < limits["matrix_relative_change"],
        "duty_derivative": derivative_error < limits["duty_row_derivative_error"],
        "provider": bool(provider["pass"] and not context["audit"].fallback_attempted),
        "calls": context["audit"].record_count < limits["logical_provider_calls"],
        "wall": wall < limits["wall_clock_sec"],
        "no_solve_or_timestep": True,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_dynamic_pressure_residual_passed"
            if passed
            else "vapor_holdup_dynamic_pressure_residual_failed"
        ),
        "decision": (
            "authorize_separately_frozen_thirty_second_pressure_dynamic_trajectory"
            if passed
            else "stop_before_pressure_dynamic_timestep"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "source_replay_parity": replay["parity"],
        "specified_condenser_duty_BTUph": specified_duty,
        "predictor_scaled_residual_inf_norm": float(np.max(np.abs(predictor))),
        "jacobian_steps": steps,
        "spectrum_relative_change": spectrum_change,
        "matrix_relative_change": matrix_change,
        "duty_row_derivative_error": derivative_error,
        "logical_provider_calls": context["audit"].record_count,
        "wall_clock_sec": wall,
        "gates": gates,
        "pass_gate": passed,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "retry_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-273 Dynamic-Pressure Residual Result",
                "",
                f"- Classification: `{report['classification']}`",
                f"- Decision: `{report['decision']}`",
                f"- Specified Qc: `{specified_duty:.6f} BTU/h`",
                f"- Predictor residual: `{report['predictor_scaled_residual_inf_norm']:.6e}`",
                f"- Jacobian ranks: `{[item['rank'] for item in steps]}`",
                f"- Jacobian conditions: `{[item['condition'] for item in steps]}`",
                f"- Matrix/spectrum changes: `{matrix_change:.6e} / {spectrum_change:.6e}`",
                f"- Provider calls/wall: `{report['logical_provider_calls']} / {wall:.3f} s`",
                f"- Gates: `{gates}`",
                "- Nonlinear solve or accepted timestep: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    np.savez_compressed(ROOT / EVIDENCE, predictor=point, jacobian_h1=matrices[0], jacobian_h2=matrices[1])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        report = prepare()
        print(json.dumps({"schema_id": report["schema_id"], "contract_payload_sha256": report["contract_payload_sha256"]}, indent=2))
        return 0
    report = execute()
    print(json.dumps({"classification": report["classification"], "pass_gate": report["pass_gate"], "failed_gates": [key for key, value in report["gates"].items() if not value]}, indent=2))
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
