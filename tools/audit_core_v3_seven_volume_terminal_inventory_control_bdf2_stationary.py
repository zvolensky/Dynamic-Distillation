#!/usr/bin/env python
"""Prepare or execute DD-197's live stationary BDF2 parity audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_seven_volume_dynamic_dae_numerical as dd171  # noqa: E402
import audit_core_v3_seven_volume_terminal_inventory_control_numerical as dd185  # noqa: E402
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    component_rate_scales,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (  # noqa: E402
    build_controlled_bdf2_history,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_bdf2_residual,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_backward_euler_residual,
    terminal_inventory_control_step_pattern,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)


SCHEMA = "dd197-core-v3-seven-volume-controlled-bdf2-stationary-contract-v1"
RESULT_SCHEMA = "dd197-core-v3-seven-volume-controlled-bdf2-stationary-result-v1"
DD184 = Path(
    "logs/dd184_core_v3_seven_volume_terminal_inventory_control_contract_20260813.json"
)
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
DD185_RESULT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_20260813.json"
)
DD196 = Path(
    "logs/dd196_core_v3_terminal_inventory_control_bdf2_kinematics_20260813.json"
)
CONTRACT = Path(
    "logs/dd197_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary_contract_20260813.json"
)
RESULT = Path(
    "logs/dd197_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_197_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_197_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary_20260813.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_kinematics_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_residual_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "tools/audit_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _rank_condition(matrix: Sequence[Sequence[float]]) -> tuple[int, float, np.ndarray]:
    values = np.asarray(matrix, dtype=float)
    singular = np.linalg.svd(values, compute_uv=False)
    tolerance = max(values.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def _relative_matrix_difference(first: np.ndarray, second: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(first)), float(np.linalg.norm(second)), 1e-15)
    return float(np.linalg.norm(first - second) / denominator)


def _dense_central_jacobian(
    objective: Callable[[np.ndarray, str], np.ndarray],
    point: np.ndarray,
    *,
    step: float,
    state_id: str,
) -> np.ndarray:
    matrix = np.empty((point.size, point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = objective(point + delta, f"{state_id}:column_{column}:plus")
        minus = objective(point - delta, f"{state_id}:column_{column}:minus")
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    return matrix


def _matrix_audit(matrix: np.ndarray, pattern: np.ndarray, tolerance: float) -> dict[str, Any]:
    rank, condition, singular = _rank_condition(matrix)
    active = np.abs(matrix) > float(tolerance)
    return {
        "rank": rank,
        "condition": condition,
        "singular_values": _vector(singular),
        "zero_rows": _vector(np.flatnonzero(~np.any(active, axis=1))),
        "zero_columns": _vector(np.flatnonzero(~np.any(active, axis=0))),
        "unexpected_couplings": int(np.count_nonzero(active & ~pattern)),
        "matrix": _rows(matrix),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-197 Controlled BDF2 Stationary Parity Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- State: accepted DD-185 seven-volume stationary controller handoff",
            f"- Constant timestep: `{payload['step_seconds']} s`",
            "- Histories: endpoint = current = prior for inventories, internal energy, and PI memory",
            "- Jacobians: dense central difference at `1e-5` and `5e-6` for BDF2; `1e-5` for backward Euler",
            "- Required rank: `58 / 58`",
            "- Nonlinear solve, accepted timestep, tuning, or trajectory: `False`",
            "",
            "Commit this immutable contract before its one live execution. The audit may evaluate residuals and Jacobians only.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-197 Controlled BDF2 Stationary Parity Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- BDF2 residual infinity norm: `{payload['bdf2_scaled_residual_inf_norm']:.6e}`",
            f"- BDF2 / BE residual difference: `{payload['bdf2_to_be_residual_max_abs']:.6e}`",
            f"- BDF2 ranks: `{payload['bdf2_jacobians'][0]['rank']} / {payload['bdf2_jacobians'][1]['rank']}`",
            f"- BE rank: `{payload['backward_euler_jacobian']['rank']}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- BDF2 spectrum step sensitivity: `{payload['bdf2_spectrum_step_change']:.6e}`",
            f"- BDF2 / BE matrix difference (diagnostic): `{payload['bdf2_to_be_matrix_relative_difference']:.6e}`",
            f"- Provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Nonlinear solve, accepted timestep, tuning, or trajectory: `False`",
            "",
        )
    )


def prepare(
    dd185_contract_path: Path,
    dd185_result_path: Path,
    dd196_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = _load(dd185_contract_path)
    result = _load(dd185_result_path)
    dd196 = _load(dd196_path)
    if not result["pass_gate"] or dd196["decision"] != "pass":
        raise RuntimeError("DD-197 prerequisites are not accepted")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (dd185_contract_path, dd185_result_path, dd196_path, DD184)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "root_solve_coordinates": source["root_solve_coordinates"],
        "controller_memory": source["controller_memory"],
        "level_setpoints": result["terminal_levels"],
        "product_reference_lbmolph": source["product_reference_lbmolph"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "step_seconds": 0.125,
        "jacobian_steps": [1.0e-5, 5.0e-6],
        "required_rank": 58,
        "limits": {
            "scaled_residual": 1.0e-8,
            "residual_parity": 1.0e-10,
            "stationary_inventory_relative_movement": 1.0e-12,
            "stationary_component_rate_lbmolph": 1.0e-8,
            "stationary_energy_rate_BTUph": 1.0e-6,
            "stationary_controller_rate_per_sec": 1.0e-12,
            "condition": 1.0e8,
            "spectrum_step_change": 0.25,
            "coupling_tolerance": 1.0e-7,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "provider_calls": 35000,
            "wall_clock_sec": 120.0
        },
        "bdf2_to_backward_euler_matrix_difference": "diagnostic_only",
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "stationary BDF2 residual or residual parity exceeds its limit",
            "stationary component, energy, controller, or inventory motion exceeds its limit",
            "any BDF2 or backward-Euler Jacobian loses rank or exceeds the condition limit",
            "BDF2 finite-difference spectrum is unstable",
            "physicality, equilibrium, conservation, provider, call, or wall gate fails"
        ],
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-197 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-197 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-197 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-197 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-197 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-197 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-197 contract is not committed")


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    dd184 = _load(DD184)
    spec = dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd171.dd168._reference(payload["reference"])
    state = dd171._state(payload["accepted_root_state"])
    contract = dd185._controlled_contract(spec, dd184)
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    point = np.asarray(payload["root_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    provider = dd171._provider(Path(payload["workbook"]), payload["property_package"])
    provider.set_exact_state_memoization(True, clear=True)
    call_audit = ProviderCallAudit()
    started = time.perf_counter()

    scale_basis = evaluate_terminal_inventory_control_residual(
        contract, spec, reference, state, provider, call_audit,
        inventory_lbmol=inventory,
        controller_memory=memory,
        level_setpoints=setpoints,
        solve_coordinates=point,
        storage_gradient_BTU_lbmol=np.zeros_like(inventory),
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=payload["product_reference_lbmolph"],
        state_id="dd197_scale_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract.base, scale_basis.base)
    storage = governing_storage_vector(spec, scale_basis.base, inventory)
    history = build_controlled_bdf2_history(
        step_seconds=payload["step_seconds"],
        current_inventory_lbmol=inventory,
        prior_inventory_lbmol=inventory,
        current_internal_energy_BTU=storage,
        prior_internal_energy_BTU=storage,
        current_controller_memory=memory,
        prior_controller_memory=memory,
    )

    def bdf2_objective(candidate: np.ndarray, state_id: str):
        return evaluate_terminal_inventory_control_bdf2_residual(
            contract, spec, reference, state, provider, call_audit,
            history=history,
            level_setpoints=setpoints,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=candidate,
            step_seconds=payload["step_seconds"],
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=payload["product_reference_lbmolph"],
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        )

    def be_objective(candidate: np.ndarray, state_id: str):
        return evaluate_terminal_inventory_control_backward_euler_residual(
            contract, spec, reference, state, provider, call_audit,
            previous_inventory_lbmol=inventory,
            previous_internal_energy_BTU=storage,
            previous_controller_memory=memory,
            level_setpoints=setpoints,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=candidate,
            step_seconds=payload["step_seconds"],
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=payload["product_reference_lbmolph"],
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        )

    bdf2_baseline = bdf2_objective(point, "dd197_bdf2_stationary")
    be_baseline = be_objective(point, "dd197_be_stationary")
    bdf2_matrices = [
        _dense_central_jacobian(
            lambda candidate, state_id: bdf2_objective(candidate, state_id).scaled,
            point,
            step=float(step),
            state_id=f"dd197_bdf2_jacobian_{step:g}",
        )
        for step in payload["jacobian_steps"]
    ]
    be_matrix = _dense_central_jacobian(
        lambda candidate, state_id: be_objective(candidate, state_id).scaled,
        point,
        step=float(payload["jacobian_steps"][0]),
        state_id="dd197_be_jacobian",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provenance = call_audit.report()

    limits = payload["limits"]
    pattern = terminal_inventory_control_step_pattern(contract)
    bdf2_audits = [
        _matrix_audit(matrix, pattern, limits["coupling_tolerance"])
        for matrix in bdf2_matrices
    ]
    be_audit = _matrix_audit(be_matrix, pattern, limits["coupling_tolerance"])
    spectrum_change = _spectrum_change(
        np.asarray(bdf2_audits[0]["singular_values"]),
        np.asarray(bdf2_audits[1]["singular_values"]),
    )
    residual_norm = float(np.max(np.abs(bdf2_baseline.scaled)))
    residual_parity = float(
        np.max(np.abs(bdf2_baseline.scaled - be_baseline.scaled))
    )
    inventory_movement = float(
        np.max(np.abs(bdf2_baseline.kinematics.endpoint_inventory_lbmol - inventory))
        / max(float(np.max(np.abs(inventory))), 1e-15)
    )
    component_rate = float(
        np.max(np.abs(bdf2_baseline.kinematics.component_rate_lbmolph))
    )
    energy_rate = float(
        np.max(np.abs(bdf2_baseline.kinematics.energy_storage_rate_BTUph))
    )
    controller_rate = float(
        np.max(np.abs(bdf2_baseline.kinematics.controller_rate_per_sec))
    )
    steady = bdf2_baseline.control_evaluation.base.steady_evaluation
    equilibrium = float(bdf2_baseline.maximum_equilibrium_residual)
    component_conservation = float(steady.component_telescoping_relative_error)
    energy_conservation = float(steady.energy_telescoping_relative_error)
    physical = bool(
        np.all(np.isfinite(bdf2_baseline.kinematics.endpoint_inventory_lbmol))
        and np.all(bdf2_baseline.kinematics.endpoint_inventory_lbmol > 0.0)
        and np.all(np.isfinite(bdf2_baseline.level_fraction))
        and np.all((bdf2_baseline.level_fraction > 0.0) & (bdf2_baseline.level_fraction < 1.0))
    )
    all_audits = [*bdf2_audits, be_audit]
    gates = {
        "bdf2_stationary_residual": residual_norm < limits["scaled_residual"],
        "bdf2_to_be_residual_parity": residual_parity < limits["residual_parity"],
        "stationary_inventory": inventory_movement < limits["stationary_inventory_relative_movement"],
        "stationary_component_rate": component_rate < limits["stationary_component_rate_lbmolph"],
        "stationary_energy_rate": energy_rate < limits["stationary_energy_rate_BTUph"],
        "stationary_controller_rate": controller_rate < limits["stationary_controller_rate_per_sec"],
        "rank": all(item["rank"] == payload["required_rank"] for item in all_audits),
        "condition": all(item["condition"] < limits["condition"] for item in all_audits),
        "structure": all(
            not item["zero_rows"] and not item["zero_columns"] and item["unexpected_couplings"] == 0
            for item in all_audits
        ),
        "bdf2_spectrum_stable": spectrum_change < limits["spectrum_step_change"],
        "physical": physical,
        "equilibrium": equilibrium < limits["equilibrium_residual"],
        "component_conservation": component_conservation < limits["component_conservation"],
        "energy_conservation": energy_conservation < limits["energy_conservation"],
        "provider": bool(provenance["pass"]),
        "provider_calls": provenance["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": "bdf2_stationary_parity_passed" if passed else "bdf2_stationary_parity_failed",
        "decision": (
            "authorize_one_frozen_bdf2_moving_step_contract"
            if passed else "stop_bdf2_before_any_solve_or_timestep"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "step_seconds": payload["step_seconds"],
        "wall_clock_sec": float(elapsed),
        "bdf2_scaled_residual_inf_norm": residual_norm,
        "backward_euler_scaled_residual_inf_norm": float(np.max(np.abs(be_baseline.scaled))),
        "bdf2_to_be_residual_max_abs": residual_parity,
        "stationary_inventory_relative_movement": inventory_movement,
        "stationary_component_rate_max_abs_lbmolph": component_rate,
        "stationary_energy_rate_max_abs_BTUph": energy_rate,
        "stationary_controller_rate_max_abs_per_sec": controller_rate,
        "maximum_equilibrium_residual": equilibrium,
        "component_conservation_relative_error": component_conservation,
        "energy_conservation_relative_error": energy_conservation,
        "level_fraction": _vector(bdf2_baseline.level_fraction),
        "bdf2_jacobians": bdf2_audits,
        "backward_euler_jacobian": be_audit,
        "worst_condition": max(item["condition"] for item in all_audits),
        "bdf2_spectrum_step_change": spectrum_change,
        "bdf2_to_be_matrix_relative_difference": _relative_matrix_difference(bdf2_matrices[0], be_matrix),
        "exact_state_memoization": memo,
        "provider": provenance,
        "gates": gates,
        "pass_gate": passed,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_tuning_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
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
    parser.add_argument("--dd185-contract", type=Path, default=DD185_CONTRACT)
    parser.add_argument("--dd185-result", type=Path, default=DD185_RESULT)
    parser.add_argument("--dd196", type=Path, default=DD196)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd185_contract,
            args.dd185_result,
            args.dd196,
            args.contract,
            args.contract_doc,
        )
        print(json.dumps({
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "campaign_executed": output["campaign_executed"],
        }, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({
            "classification": output["classification"],
            "pass_gate": output["pass_gate"],
            "decision": output["decision"],
        }, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
