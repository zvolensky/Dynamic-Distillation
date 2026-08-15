#!/usr/bin/env python
"""Prepare or execute the frozen DD-233 full-column zero-motion audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
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

import audit_core_v3_aligned_pr_density_parity as dd229  # noqa: E402
import audit_core_v3_full_c3c4_dynamic_handoff as dd232  # noqa: E402
import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
import run_core_v3_full_c3c4_steady_root as dd223  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    component_rate_scales,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (  # noqa: E402
    coordinate_layout,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (  # noqa: E402
    build_controlled_bdf2_history,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_bdf2_residual,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    TerminalPIParameters,
    TerminalVesselGeometry,
    audit_terminal_inventory_control_contract,
    build_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    terminal_inventory_control_step_pattern,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)


SCHEMA = "dd233-core-v3-full-c3c4-zero-motion-contract-v1"
RESULT_SCHEMA = "dd233-core-v3-full-c3c4-zero-motion-result-v1"
DD221 = dd232.DD221
DD230 = Path("logs/dd230_core_v3_full_c3c4_coordinate_scaling_20260815.json")
DD231_CONTRACT = dd232.DD231_CONTRACT
DD231_RESULT = dd232.DD231_RESULT
DD232 = Path("logs/dd232_core_v3_full_c3c4_dynamic_handoff_20260815.json")
CONTRACT = Path("logs/dd233_core_v3_full_c3c4_zero_motion_contract_20260815.json")
RESULT = Path("logs/dd233_core_v3_full_c3c4_zero_motion_20260815")
CONTRACT_DOC = Path("docs/dd_233_core_v3_full_c3c4_zero_motion_contract_20260815.md")
RESULT_DOC = Path("docs/dd_233_core_v3_full_c3c4_zero_motion_20260815.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_kinematics_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_residual_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "tools/audit_core_v3_aligned_pr_density_parity.py",
    "tools/audit_core_v3_full_c3c4_dynamic_handoff.py",
    "tools/audit_core_v3_full_c3c4_zero_motion.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape(-1)]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _controlled_contract(spec: Any, handoff: Mapping[str, Any]):
    base = dd232.build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=str(DD231_RESULT).replace("\\", "/"),
        product_flow_parameters=("D_dd231_root", "B_dd231_root"),
    )
    return build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(**handoff["terminal_geometry"]),
        controllers=TerminalPIParameters(**handoff["controller_parameters"]),
    )


def _adapted_coordinate_scale(
    spec: Any,
    controlled: Any,
    stationary_scale: Sequence[float],
) -> np.ndarray:
    layout = coordinate_layout(spec)
    stationary = np.asarray(stationary_scale, dtype=float)
    algebraic_indices = dd232.dynamic_algebraic_indices(spec)
    base_rate_count = len(controlled.base.derivative_variables)
    result = np.concatenate(
        (
            np.ones(base_rate_count + 2, dtype=float),
            stationary[algebraic_indices],
            stationary[[layout.distillate, layout.bottoms]],
        )
    )
    if result.shape != (len(controlled.rows),) or np.any(result <= 0.0):
        raise RuntimeError("DD-233 adapted coordinate scale is invalid")
    return result


def _sentinel_indices(variable_names: Sequence[str]) -> tuple[int, ...]:
    names = tuple(variable_names)
    families = (
        "dN[",
        "dI_level[",
        "T[",
        "y[",
        "L[",
        "V[",
        "y_bubble[",
        "Q_C",
        "log_product_ratio[",
    )
    selected: list[int] = []
    for family in families:
        matches = [index for index, name in enumerate(names) if name.startswith(family)]
        if matches:
            selected.extend((matches[0], matches[-1]))
    return tuple(dict.fromkeys(selected))


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    dd221 = _load(DD221)
    scaling = _load(DD230)
    root_contract = _load(DD231_CONTRACT)
    root_result = _load(DD231_RESULT)
    handoff = _load(DD232)
    if not (
        dd221.get("pass_gate")
        and scaling.get("pass_gate")
        and root_result.get("campaign_pass")
        and handoff.get("pass_gate")
    ):
        raise RuntimeError("DD-233 prerequisites are not accepted")
    model_contract_path = Path(root_contract["source_model_contract"])
    model_contract = _load(model_contract_path)
    spec = dd223.dd222._spec(
        model_contract["source_mapping"],
        float(model_contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    controlled = _controlled_contract(spec, handoff)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or len(controlled.rows) != 162:
        raise RuntimeError("DD-233 controlled structural prerequisite changed")
    variable_names = tuple(
        variable.name
        for variable in (*controlled.derivative_variables, *controlled.algebraic_variables)
    )
    coordinate_scale = _adapted_coordinate_scale(
        spec, controlled, scaling["coordinate_scale"]
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(path)
            for path in (
                DD221,
                DD230,
                DD231_CONTRACT,
                DD231_RESULT,
                DD232,
                model_contract_path,
            )
        },
        "model_contract": str(model_contract_path).replace("\\", "/"),
        "workbook": model_contract["workbook"],
        "workbook_sha256": model_contract["workbook_sha256"],
        "provider_routing": handoff["provider_routing"],
        "accepted_root_state": handoff["accepted_root_state"],
        "inventory_lbmol": handoff["component_inventory_lbmol"],
        "root_solve_coordinates": handoff["controlled_root_solve_coordinates"],
        "controller_memory": handoff["controller_memory"],
        "product_reference_lbmolph": handoff["product_reference_lbmolph"],
        "terminal_geometry": handoff["terminal_geometry"],
        "controller_parameters": handoff["controller_parameters"],
        "fixed_steady_residual_scales": model_contract["fixed_residual_scales"],
        "step_seconds": 0.25,
        "jacobian_steps": [1.0e-5, 5.0e-6],
        "coordinate_scale": _vector(coordinate_scale),
        "coordinate_scale_source": str(DD230).replace("\\", "/"),
        "variable_names": list(variable_names),
        "sentinel_indices": list(_sentinel_indices(variable_names)),
        "required_rank": 162,
        "limits": {
            "scaled_residual": 1.0e-8,
            "stationary_inventory_relative_movement": 1.0e-12,
            "stationary_component_rate_lbmolph": 1.0e-8,
            "stationary_energy_rate_BTUph": 1.0e-6,
            "stationary_controller_rate_per_sec": 1.0e-12,
            "level_error": 1.0e-12,
            "minimum_level_fraction": 0.01,
            "maximum_level_fraction": 0.99,
            "condition": 1.0e8,
            "spectrum_step_change": 0.25,
            "sentinel_relative_difference": 1.0e-6,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-10,
            "energy_conservation": 1.0e-10,
            "provider_calls": 150000,
            "wall_clock_sec": 300.0,
        },
        "structural_audit": asdict(structural),
        "implementation_sha256": {path: _sha(Path(path)) for path in IMPLEMENTATION},
        "hard_stops": [
            "the zero-motion residual or any stationary-rate gate fails",
            "either leading Jacobian loses rank, exceeds 1e8 condition, or has unstable spectra",
            "a direct sentinel column disagrees with the colored matrix",
            "a physicality, level, equilibrium, conservation, or provider gate fails",
            "the call or wall limit is exceeded",
        ],
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "controller_state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-233 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-233 Full-C3/C4 Zero-Motion Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- State: accepted DD-231 20-stage stationary root",
            "- Dynamic system: controlled constant-step BDF2, `162 x 162`",
            f"- History timestep: `{payload['step_seconds']} s`",
            "- Histories: accepted inventory/energy/memory repeated at both levels",
            "- Thermo: DWSIM fugacity/enthalpy; aligned-PR liquid density",
            "- Jacobians: colored central differences at `1e-5` and `5e-6`",
            f"- Direct sentinel columns: `{len(payload['sentinel_indices'])}`",
            "- Solve, accepted timestep, controller advance, or integration: `False`",
            "",
            "One execution is permitted after this contract is committed.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-233 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-233 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-233 implementation changed: {path}")
    if hashlib.sha256(Path(payload["workbook"]).read_bytes()).hexdigest() != payload["workbook_sha256"]:
        raise RuntimeError("DD-233 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-233 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition, singular


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def _direct_column(
    objective: Callable[[np.ndarray, str], np.ndarray],
    point: np.ndarray,
    column: int,
    *,
    step: float,
    state_id: str,
) -> np.ndarray:
    delta = np.zeros_like(point)
    delta[column] = float(step)
    plus = objective(point + delta, f"{state_id}:plus")
    minus = objective(point - delta, f"{state_id}:minus")
    return (plus - minus) / (2.0 * float(step))


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    model_contract = _load(Path(payload["model_contract"]))
    _workbook, dwsim, spec, reference = dd223._source_model(model_contract)
    aligned = dd092._independent_provider(model_contract)
    provider = dd229.DensityRoutedProvider(dwsim, aligned)
    handoff = _load(DD232)
    controlled = _controlled_contract(spec, handoff)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or len(controlled.rows) != payload["required_rank"]:
        raise RuntimeError("DD-233 structural contract changed")
    state = dd232._state(payload["accepted_root_state"])
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    point = np.asarray(payload["root_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    coordinate_scale = np.asarray(payload["coordinate_scale"], dtype=float)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider.set_exact_state_memoization(True, clear=True)
    started = time.perf_counter()

    seed = evaluate_terminal_inventory_control_residual(
        controlled,
        spec,
        reference,
        state,
        provider,
        audit,
        inventory_lbmol=inventory,
        controller_memory=memory,
        level_setpoints=TerminalLevelSetpoints(0.5, 0.5),
        solve_coordinates=point,
        storage_gradient_BTU_lbmol=np.zeros_like(inventory),
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=product_reference,
        state_id="dd233_history_and_level_reconstruction",
        evaluation_kind="residual",
    )
    setpoints = TerminalLevelSetpoints(*seed.level_fraction)
    rate_scales = component_rate_scales(controlled.base, seed.base)
    storage = governing_storage_vector(spec, seed.base, inventory)
    history = build_controlled_bdf2_history(
        step_seconds=payload["step_seconds"],
        current_inventory_lbmol=inventory,
        prior_inventory_lbmol=inventory,
        current_internal_energy_BTU=storage,
        prior_internal_energy_BTU=storage,
        current_controller_memory=memory,
        prior_controller_memory=memory,
    )

    def physical_objective(candidate: np.ndarray, state_id: str):
        return evaluate_terminal_inventory_control_bdf2_residual(
            controlled,
            spec,
            reference,
            state,
            provider,
            audit,
            history=history,
            level_setpoints=setpoints,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=candidate,
            step_seconds=payload["step_seconds"],
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=product_reference,
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        )

    baseline = physical_objective(point, "dd233_zero_motion_baseline")
    origin = np.zeros_like(point)

    def scaled_objective(offset: np.ndarray, state_id: str) -> np.ndarray:
        return physical_objective(point + coordinate_scale * offset, state_id).scaled

    pattern = terminal_inventory_control_step_pattern(controlled)
    matrices: list[np.ndarray] = []
    groups: list[tuple[tuple[int, ...], ...]] = []
    for step in payload["jacobian_steps"]:
        matrix, color_groups = colored_central_difference_jacobian(
            scaled_objective,
            origin,
            pattern=pattern,
            step=float(step),
            state_id=f"dd233_jacobian_{step:g}",
        )
        matrices.append(matrix)
        groups.append(color_groups)
    sentinel_differences: dict[str, float] = {}
    first_step = float(payload["jacobian_steps"][0])
    for column in payload["sentinel_indices"]:
        direct = _direct_column(
            scaled_objective,
            origin,
            int(column),
            step=first_step,
            state_id=f"dd233_sentinel_{column}_jacobian",
        )
        denominator = max(
            float(np.linalg.norm(direct)),
            float(np.linalg.norm(matrices[0][:, int(column)])),
            1.0e-15,
        )
        sentinel_differences[payload["variable_names"][int(column)]] = float(
            np.linalg.norm(direct - matrices[0][:, int(column)]) / denominator
        )

    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provenance = audit.report()
    matrix_reports = []
    for step, matrix, color_groups in zip(
        payload["jacobian_steps"], matrices, groups, strict=True
    ):
        rank, condition, singular = _rank_condition(matrix)
        matrix_reports.append(
            {
                "step": float(step),
                "color_count": len(color_groups),
                "rank": rank,
                "condition": condition,
                "singular_values": _vector(singular),
                "zero_rows": _vector(np.flatnonzero(np.max(np.abs(matrix), axis=1) <= 1.0e-12)),
                "zero_columns": _vector(np.flatnonzero(np.max(np.abs(matrix), axis=0) <= 1.0e-12)),
                "matrix": _rows(matrix),
            }
        )
    spectrum_change = _spectrum_change(
        np.asarray(matrix_reports[0]["singular_values"]),
        np.asarray(matrix_reports[1]["singular_values"]),
    )
    steady = baseline.control_evaluation.base.steady_evaluation
    limits = payload["limits"]
    residual_norm = float(np.max(np.abs(baseline.scaled)))
    inventory_movement = float(
        np.max(np.abs(baseline.kinematics.endpoint_inventory_lbmol - inventory))
        / max(float(np.max(np.abs(inventory))), 1.0e-15)
    )
    component_rate = float(np.max(np.abs(baseline.kinematics.component_rate_lbmolph)))
    energy_rate = float(np.max(np.abs(baseline.kinematics.energy_storage_rate_BTUph)))
    controller_rate = float(np.max(np.abs(baseline.kinematics.controller_rate_per_sec)))
    level_error = float(np.max(np.abs(baseline.level_error)))
    equilibrium = float(baseline.maximum_equilibrium_residual)
    component_conservation = float(steady.component_telescoping_relative_error)
    energy_conservation = float(steady.energy_telescoping_relative_error)
    physical = bool(
        np.all(baseline.kinematics.endpoint_inventory_lbmol > 0.0)
        and np.all(np.isfinite(baseline.level_fraction))
        and np.all(baseline.level_fraction > limits["minimum_level_fraction"])
        and np.all(baseline.level_fraction < limits["maximum_level_fraction"])
        and np.all(baseline.control_evaluation.base.physical_state.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(baseline.control_evaluation.base.physical_state.vapor_flow_lbmolph > 0.0)
    )
    gates = {
        "structural": structural.pass_gate,
        "zero_motion_residual": residual_norm < limits["scaled_residual"],
        "stationary_inventory": inventory_movement < limits["stationary_inventory_relative_movement"],
        "stationary_component_rate": component_rate < limits["stationary_component_rate_lbmolph"],
        "stationary_energy_rate": energy_rate < limits["stationary_energy_rate_BTUph"],
        "stationary_controller_rate": controller_rate < limits["stationary_controller_rate_per_sec"],
        "zero_level_error": level_error < limits["level_error"],
        "physical": physical,
        "rank": all(item["rank"] == payload["required_rank"] for item in matrix_reports),
        "condition": all(item["condition"] < limits["condition"] for item in matrix_reports),
        "no_zero_rows_or_columns": all(
            not item["zero_rows"] and not item["zero_columns"] for item in matrix_reports
        ),
        "spectrum_stable": spectrum_change < limits["spectrum_step_change"],
        "sentinel_columns": max(sentinel_differences.values(), default=0.0)
        < limits["sentinel_relative_difference"],
        "equilibrium": equilibrium < limits["equilibrium_residual"],
        "component_conservation": component_conservation < limits["component_conservation"],
        "energy_conservation": energy_conservation < limits["energy_conservation"],
        "provider": bool(provenance["pass"]),
        "provider_calls": provenance["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "full_c3c4_zero_motion_audit_passed"
            if passed
            else "full_c3c4_zero_motion_audit_failed"
        ),
        "decision": (
            "authorize_one_separately_frozen_full_c3c4_stationary_hold_step"
            if passed
            else "stop_before_any_full_c3c4_timestep"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "step_seconds": payload["step_seconds"],
        "zero_motion_scaled_residual_inf_norm": residual_norm,
        "stationary_inventory_relative_movement": inventory_movement,
        "stationary_component_rate_max_abs_lbmolph": component_rate,
        "stationary_energy_rate_max_abs_BTUph": energy_rate,
        "stationary_controller_rate_max_abs_per_sec": controller_rate,
        "terminal_levels": asdict(setpoints),
        "maximum_level_error": level_error,
        "internal_energy_BTU": _vector(storage),
        "rate_scales_lbmolph": _rows(rate_scales),
        "maximum_equilibrium_residual": equilibrium,
        "component_conservation_relative_error": component_conservation,
        "energy_conservation_relative_error": energy_conservation,
        "jacobians": matrix_reports,
        "spectrum_relative_change": spectrum_change,
        "sentinel_relative_differences": sentinel_differences,
        "provider": provenance,
        "exact_state_memoization": memo,
        "wall_clock_sec": float(elapsed),
        "gates": gates,
        "pass_gate": passed,
        "nonlinear_solve_attempted": False,
        "controller_state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(report), encoding="utf-8")
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    ranks = " / ".join(str(item["rank"]) for item in payload["jacobians"])
    conditions = " / ".join(f"{item['condition']:.6e}" for item in payload["jacobians"])
    levels = payload["terminal_levels"]
    return "\n".join(
        (
            "# DD-233 Full-C3/C4 Zero-Motion Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Scaled residual infinity norm: `{payload['zero_motion_scaled_residual_inf_norm']:.6e}`",
            f"- Component / energy / PI maximum rates: `{payload['stationary_component_rate_max_abs_lbmolph']:.6e}` / `{payload['stationary_energy_rate_max_abs_BTUph']:.6e}` / `{payload['stationary_controller_rate_max_abs_per_sec']:.6e}`",
            f"- Top / bottom levels: `{levels['top_fraction']:.6f}` / `{levels['bottom_fraction']:.6f}`",
            f"- Jacobian ranks: `{ranks}`",
            f"- Jacobian conditions: `{conditions}`",
            f"- Spectrum step change: `{payload['spectrum_relative_change']:.6e}`",
            f"- Provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Solve, controller advance, accepted timestep, or integration: `False`",
            "",
        )
    )


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


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "required_rank": report["required_rank"],
                    "sentinel_count": len(report["sentinel_indices"]),
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
