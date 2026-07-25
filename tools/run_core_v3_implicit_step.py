#!/usr/bin/env python
"""Prepare or execute the frozen DD-097 Core V3 implicit-step campaign."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    BackwardEulerEvaluation,
    ImplicitSolveOutcome,
    ImplicitStepSettings,
    solve_backward_euler_step,
    solve_zero_rate_algebraic,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA_ID = "dd097-core-v3-implicit-step-contract-v1"
RESULT_SCHEMA_ID = "dd097-core-v3-implicit-step-result-v1"
DEFAULT_DD096_CONTRACT = Path(
    "logs/dd096_core_v3_dynamic_dae_numerical_contract_20260725.json"
)
DEFAULT_DD096_RESULT = Path(
    "logs/dd096_core_v3_dynamic_dae_numerical_20260725.json"
)
DEFAULT_CONTRACT = Path("logs/dd097_core_v3_implicit_step_contract_20260725.json")
DEFAULT_RESULT = Path("logs/dd097_core_v3_implicit_step_20260725.json")

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tests/test_core_v3_implicit_step_v1.py",
    "tools/run_core_v3_implicit_step.py",
    "docs/dd_097_core_v3_implicit_step_contract_20260725.md",
)

SETTINGS = ImplicitStepSettings()
STEP_SECONDS = (1.0, 0.5)
LIMITS = {
    "scaled_residual": 1.0e-8,
    "condition": 1.0e8,
    "zero_algebraic_movement": 1.0e-7,
    "component_rate_lbmolph": 1.0e-4,
    "relative_inventory_movement": 1.0e-9,
    "algebraic_movement": 1.0e-7,
    "bubble_residual": 1.0e-10,
    "component_conservation": 1.0e-8,
    "energy_conservation": 1.0e-8,
    "refinement_inventory": 1.0e-9,
    "refinement_rate_coordinate": 1.0e-7,
    "refinement_algebraic": 1.0e-7,
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [
        [float(value) for value in np.asarray(row, dtype=float).reshape((-1,))]
        for row in np.asarray(values, dtype=float)
    ]


def _spec(source: Mapping[str, Any], feed_enthalpy: float) -> OperatingSpec:
    return OperatingSpec(
        component_names=tuple(source["component_names"]),
        pressure_psia=np.asarray(source["pressure_psia"], dtype=float),
        reflux_lbmolph=float(source["reflux_lbmolph"]),
        feed_component_lbmolph=np.asarray(
            source["feed_component_lbmolph"], dtype=float
        ),
        feed_enthalpy_BTUph=float(feed_enthalpy),
        reboiler_duty_BTUph=float(source["reboiler_duty_BTUph"]),
        terminal_liquid_targets_lbmol=np.asarray(
            source["terminal_liquid_targets_lbmol"], dtype=float
        ),
        hydraulic_geometry=tuple(
            HydraulicGeometry(**item) for item in source["hydraulic_geometry"]
        ),
    )


def _reference(payload: Mapping[str, Any]) -> NumericalReference:
    return NumericalReference(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(
            payload["liquid_mole_fraction"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(payload["vapor_mole_fraction"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_reference_BTUph=float(
            payload["condenser_duty_reference_BTUph"]
        ),
        condenser_duty_scale_BTUph=float(payload["condenser_duty_scale_BTUph"]),
    )


def _state(payload: Mapping[str, Any]) -> PhysicalState:
    return PhysicalState(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(
            payload["liquid_mole_fraction"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(payload["vapor_mole_fraction"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
    )


def _provider(workbook: Path, package: str) -> ThermoProviderV1:
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    return ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=package,
        silence_backend_console=True,
    )


def _rank_condition(matrix: Sequence[Sequence[float]]) -> tuple[int, float]:
    values = np.asarray(matrix, dtype=float)
    singular = np.linalg.svd(values, compute_uv=False)
    tolerance = max(values.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-097 Frozen Core V3 Implicit-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Solver: `least_squares(method=trf)`",
            "- Checks: zero-rate recovery, independent `1.0 s` and `0.5 s` steps",
            "- Live property evaluation during preparation: `False`",
            "- Dynamic step during preparation: `False`",
            "",
            "The contract must be committed before its one live execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    return "\n".join(
        (
            "# DD-097 Core V3 Implicit-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Zero-rate residual: `{payload['zero_rate']['residual_inf_norm']:.6e}`",
            f"- Step residuals: `{steps[0]['residual_inf_norm']:.6e}`, "
            f"`{steps[1]['residual_inf_norm']:.6e}`",
            f"- Step ranks: `{steps[0]['jacobian_rank']}`, "
            f"`{steps[1]['jacobian_rank']}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Provider gate: `{payload['provider_provenance']['pass']}`",
            f"- Multi-step trajectory attempted: `{payload['trajectory_attempted']}`",
            "",
        )
    )


def prepare(
    dd096_contract_path: Path,
    dd096_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd096_contract_path)
    result = _load(dd096_result_path)
    if not result["pass"] or result["decision"] != "authorize_implicit_solver_contract_only":
        raise RuntimeError("DD-097 requires the accepted DD-096 result")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd096_contract_path": str(dd096_contract_path).replace("\\", "/"),
        "dd096_contract_sha256": _sha256(ROOT / dd096_contract_path),
        "dd096_result_path": str(dd096_result_path).replace("\\", "/"),
        "dd096_result_sha256": _sha256(ROOT / dd096_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "accepted_root_algebraic_coordinates": source[
            "accepted_root_algebraic_coordinates"
        ],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": {
            "method": SETTINGS.method,
            "ftol": SETTINGS.ftol,
            "xtol": SETTINGS.xtol,
            "gtol": SETTINGS.gtol,
            "max_nfev": SETTINGS.max_nfev,
            "x_scale": SETTINGS.x_scale,
            "jacobian_step": SETTINGS.jacobian_step,
            "bounds": None,
        },
        "step_seconds": list(STEP_SECONDS),
        "limits": LIMITS,
        "required_zero_algebraic_rank": 23,
        "required_step_rank": 38,
        "hard_stops": [
            "any nonlinear solve or residual gate fails",
            "zero-rate or finite-step Jacobian rank or condition fails",
            "stationary rate, inventory, algebraic, or refinement gate fails",
            "physicality, storage bubble, or conservation gate fails",
            "provider ownership or no-fallback gate fails",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION_PATHS
        },
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_step_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify_execution_contract(
    payload: dict[str, Any], contract_path: Path, result_path: Path
) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-097 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-097 implementation changed: {path}")
    if _sha256(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-097 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-097 result already exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-097 contract is not committed")


def _settings(payload: Mapping[str, Any]) -> ImplicitStepSettings:
    values = payload["solver"]
    return ImplicitStepSettings(
        method=str(values["method"]),
        ftol=float(values["ftol"]),
        xtol=float(values["xtol"]),
        gtol=float(values["gtol"]),
        max_nfev=int(values["max_nfev"]),
        x_scale=float(values["x_scale"]),
        jacobian_step=float(values["jacobian_step"]),
    )


def _provider_summary(call_audit: ProviderCallAudit) -> dict[str, Any]:
    counts = Counter(
        (record.provider_interface, record.evaluation_kind)
        for record in call_audit.records
    )
    violations = call_audit.violations()
    return {
        "total_calls": len(call_audit.records),
        "counts": [
            {
                "provider_interface": key[0],
                "evaluation_kind": key[1],
                "count": int(value),
            }
            for key, value in sorted(counts.items())
        ],
        "violations": list(violations),
        "fallback_attempted": bool(call_audit.fallback_attempted),
        "pass": not violations,
    }


def _basic_outcome(outcome: ImplicitSolveOutcome) -> dict[str, Any]:
    rank, condition = _rank_condition(outcome.jacobian)
    return {
        "success": outcome.success,
        "status": outcome.status,
        "message": outcome.message,
        "nfev": outcome.nfev,
        "njev": outcome.njev,
        "cost": outcome.cost,
        "optimality": outcome.optimality,
        "wall_clock_sec": outcome.wall_clock_sec,
        "residual_inf_norm": float(np.max(np.abs(outcome.final_residual))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "coordinate_movement_inf_norm": float(
            np.max(np.abs(outcome.final_coordinates - outcome.initial_coordinates))
        ),
    }


def _step_report(
    outcome: ImplicitSolveOutcome,
    spec: OperatingSpec,
    previous_inventory: np.ndarray,
    step_seconds: float,
) -> dict[str, Any]:
    if not isinstance(outcome.evaluation, BackwardEulerEvaluation):
        raise TypeError("finite-step outcome lacks backward-Euler evaluation")
    evaluation = outcome.evaluation
    state = evaluation.dynamic_evaluation.physical_state
    properties = evaluation.dynamic_evaluation.steady_evaluation.properties
    component_external = (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )
    component_error = np.sum(evaluation.component_rate_lbmolph, axis=0) - component_external
    component_denominator = max(
        float(np.max(np.abs(spec.feed_component_lbmolph))),
        float(np.max(np.abs(component_external))),
        1.0,
    )
    energy_external = (
        float(spec.feed_enthalpy_BTUph)
        + float(spec.reboiler_duty_BTUph)
        + float(state.condenser_duty_BTUph)
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )
    energy_error = float(np.sum(evaluation.energy_storage_rate_BTUph) - energy_external)
    energy_denominator = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(state.condenser_duty_BTUph)),
        abs(float(energy_external)),
        1.0,
    )
    height_indices = [VOLUME_IDS.index(volume) for volume in HYDRAULIC_VOLUME_IDS]
    heights = np.asarray(properties.liquid_height_ft, dtype=float)[height_indices]
    spacings = np.asarray(
        [geometry.tray_spacing_ft for geometry in spec.hydraulic_geometry], dtype=float
    )
    physical = {
        "positive_inventory": bool(np.all(evaluation.endpoint_inventory_lbmol > 0.0)),
        "positive_liquid_composition": bool(np.all(state.liquid_mole_fraction > 0.0)),
        "positive_vapor_composition": bool(np.all(state.vapor_mole_fraction > 0.0)),
        "positive_bubble_composition": bool(
            np.all(state.bubble_vapor_mole_fraction > 0.0)
        ),
        "positive_flows": bool(
            np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(state.vapor_flow_lbmolph > 0.0)
        ),
        "ordered_temperature": bool(np.all(np.diff(state.temperature_F) > 0.0)),
        "negative_condenser_duty": bool(state.condenser_duty_BTUph < 0.0),
        "hydraulic_height_below_spacing": bool(np.all(heights < spacings)),
        "all_finite": bool(
            np.all(np.isfinite(evaluation.endpoint_inventory_lbmol))
            and np.all(np.isfinite(state.temperature_F))
            and np.all(np.isfinite(state.vapor_flow_lbmolph))
        ),
    }
    report = _basic_outcome(outcome)
    report.update(
        {
            "step_seconds": float(step_seconds),
            "component_rate_max_abs_lbmolph": float(
                np.max(np.abs(evaluation.component_rate_lbmolph))
            ),
            "relative_inventory_movement_max": float(
                np.max(
                    np.abs(evaluation.endpoint_inventory_lbmol - previous_inventory)
                    / previous_inventory
                )
            ),
            "algebraic_movement_inf_norm": float(
                np.max(
                    np.abs(
                        evaluation.algebraic_coordinates
                        - outcome.initial_coordinates[len(evaluation.rate_coordinates.reshape((-1,))) :]
                    )
                )
            ),
            "component_conservation_relative_error": float(
                np.max(np.abs(component_error)) / component_denominator
            ),
            "energy_conservation_relative_error": float(
                abs(energy_error) / energy_denominator
            ),
            "maximum_bubble_residual": evaluation.maximum_bubble_residual,
            "inventory_lbmol": _rows(evaluation.endpoint_inventory_lbmol),
            "rate_coordinates": _rows(evaluation.rate_coordinates),
            "algebraic_coordinates": _vector(evaluation.algebraic_coordinates),
            "temperature_F": _vector(state.temperature_F),
            "physical": physical,
            "physical_pass": all(physical.values()),
        }
    )
    return report


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify_execution_contract(payload, contract_path, result_path)
    source = payload["source_mapping"]
    spec = _spec(source, float(payload["operating_spec"]["feed_enthalpy_BTUph"]))
    reference = _reference(payload["reference"])
    state = _state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(spec.component_names)
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-097 inventory mapping changed")
    if not np.allclose(algebraic, payload["accepted_root_algebraic_coordinates"]):
        raise RuntimeError("DD-097 algebraic mapping changed")
    provider = _provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    settings = _settings(payload)
    started = time.perf_counter()
    zero = solve_zero_rate_algebraic(
        contract,
        spec,
        reference,
        state,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        initial_algebraic_coordinates=algebraic,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        settings=settings,
        name="dd097_zero_rate",
    )
    step_outcomes = [
        solve_backward_euler_step(
            contract,
            spec,
            reference,
            state,
            provider,
            call_audit,
            previous_inventory_lbmol=inventory,
            initial_algebraic_coordinates=algebraic,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step_seconds=float(step),
            settings=settings,
            name=f"dd097_step_{step:g}s",
        )
        for step in payload["step_seconds"]
    ]
    wall_clock = float(time.perf_counter() - started)
    zero_report = _basic_outcome(zero)
    step_reports = [
        _step_report(outcome, spec, inventory, float(step))
        for outcome, step in zip(step_outcomes, payload["step_seconds"])
    ]
    first_eval = step_outcomes[0].evaluation
    second_eval = step_outcomes[1].evaluation
    if not isinstance(first_eval, BackwardEulerEvaluation) or not isinstance(
        second_eval, BackwardEulerEvaluation
    ):
        raise TypeError("DD-097 refinement outcomes are invalid")
    refinement = {
        "relative_inventory_difference": float(
            np.max(
                np.abs(
                    first_eval.endpoint_inventory_lbmol
                    - second_eval.endpoint_inventory_lbmol
                )
                / inventory
            )
        ),
        "rate_coordinate_difference": float(
            np.max(np.abs(first_eval.rate_coordinates - second_eval.rate_coordinates))
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(
                    first_eval.algebraic_coordinates
                    - second_eval.algebraic_coordinates
                )
            )
        ),
    }
    provider_report = _provider_summary(call_audit)
    limits = payload["limits"]
    zero_gates = {
        "success": zero.success and zero.nfev <= int(payload["solver"]["max_nfev"]),
        "residual": zero_report["residual_inf_norm"] < float(limits["scaled_residual"]),
        "rank": zero_report["jacobian_rank"]
        == int(payload["required_zero_algebraic_rank"]),
        "condition": zero_report["jacobian_condition"] < float(limits["condition"]),
        "movement": zero_report["coordinate_movement_inf_norm"]
        < float(limits["zero_algebraic_movement"]),
    }
    step_gates: list[dict[str, bool]] = []
    for report in step_reports:
        step_gates.append(
            {
                "success": bool(report["success"])
                and int(report["nfev"]) <= int(payload["solver"]["max_nfev"]),
                "residual": float(report["residual_inf_norm"])
                < float(limits["scaled_residual"]),
                "rank": int(report["jacobian_rank"])
                == int(payload["required_step_rank"]),
                "condition": float(report["jacobian_condition"])
                < float(limits["condition"]),
                "stationary_rate": float(report["component_rate_max_abs_lbmolph"])
                < float(limits["component_rate_lbmolph"]),
                "stationary_inventory": float(report["relative_inventory_movement_max"])
                < float(limits["relative_inventory_movement"]),
                "stationary_algebraic": float(report["algebraic_movement_inf_norm"])
                < float(limits["algebraic_movement"]),
                "storage_bubble": float(report["maximum_bubble_residual"])
                < float(limits["bubble_residual"]),
                "component_conservation": float(
                    report["component_conservation_relative_error"]
                )
                < float(limits["component_conservation"]),
                "energy_conservation": float(
                    report["energy_conservation_relative_error"]
                )
                < float(limits["energy_conservation"]),
                "physical": bool(report["physical_pass"]),
            }
        )
    refinement_gates = {
        "inventory": refinement["relative_inventory_difference"]
        < float(limits["refinement_inventory"]),
        "rate": refinement["rate_coordinate_difference"]
        < float(limits["refinement_rate_coordinate"]),
        "algebraic": refinement["algebraic_coordinate_difference"]
        < float(limits["refinement_algebraic"]),
    }
    passed = (
        all(zero_gates.values())
        and all(all(gates.values()) for gates in step_gates)
        and all(refinement_gates.values())
        and bool(provider_report["pass"])
    )
    worst_condition = max(
        [zero_report["jacobian_condition"]]
        + [report["jacobian_condition"] for report in step_reports]
    )
    result = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd097_core_v3_implicit_step_passed"
            if passed
            else "dd097_core_v3_implicit_step_failed"
        ),
        "decision": (
            "authorize_short_open_loop_trajectory_contract_only"
            if passed
            else "stop_implicit_step_path"
        ),
        "wall_clock_sec": wall_clock,
        "zero_rate": zero_report,
        "steps": step_reports,
        "refinement": refinement,
        "provider_provenance": provider_report,
        "zero_rate_gates": zero_gates,
        "step_gates": step_gates,
        "refinement_gates": refinement_gates,
        "worst_condition": float(worst_condition),
        "pass": passed,
        "campaign_executed_once": True,
        "controller_attempted": False,
        "disturbance_attempted": False,
        "trajectory_attempted": False,
    }
    destination = ROOT / result_path
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd096-contract", type=Path, default=DEFAULT_DD096_CONTRACT)
    parser.add_argument("--dd096-result", type=Path, default=DEFAULT_DD096_RESULT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd096_contract, args.dd096_result, args.contract)
        print(json.dumps(output, indent=2))
        raise SystemExit(0)
    output = execute(args.contract, args.result)
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if output["pass"] else 2)
