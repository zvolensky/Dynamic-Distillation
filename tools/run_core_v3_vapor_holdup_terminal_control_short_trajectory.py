#!/usr/bin/env python
"""Prepare or execute DD-267's short controlled vapor-holdup trajectory."""

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
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_stationary_hold as dd248  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_stationary_hold as dd265  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_implicit_residual_v1 import (  # noqa: E402
    controlled_implicit_initial_coordinates,
    evaluate_vapor_holdup_terminal_control_implicit_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (  # noqa: E402
    vapor_holdup_terminal_control_pattern,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402


SCHEMA = "dd267-core-v3-c3c4-vapor-holdup-terminal-control-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd267-core-v3-c3c4-vapor-holdup-terminal-control-short-trajectory-result-v1"
CONTRACT = Path(
    "logs/dd267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_contract_20260820.json"
)
RESULT = Path(
    "logs/dd267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_20260820.json"
)
EVIDENCE = Path(
    "logs/dd267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_20260820.npz"
)
JOURNAL = Path(
    "logs/dd267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_journal_20260820"
)
CONTRACT_DOC = Path(
    "docs/dd_267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_20260820.md"
)
SOURCE_HOLD = dd265.DEFAULT_JSON
SOURCE_HOLD_EVIDENCE = dd265.DEFAULT_MATRIX
SOURCE_ADJUDICATION = Path(
    "logs/dd266_core_v3_c3c4_vapor_holdup_terminal_control_hold_adjudication_20260820.json"
)
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_terminal_control_short_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_terminal_control_stationary_hold.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_terminal_control_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_terminal_control_contract_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/colored_jacobian_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    hold = json.loads((ROOT / SOURCE_HOLD).read_text(encoding="utf-8"))
    adjudication = json.loads(
        (ROOT / SOURCE_ADJUDICATION).read_text(encoding="utf-8")
    )
    if hold.get("pass_gate") or not adjudication.get("pass_gate"):
        raise RuntimeError("DD-267 requires the preserved DD-265/DD-266 decisions")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": (
            "DD-266 authorizes one separately frozen short controlled trajectory"
        ),
        "sources": {
            SOURCE_HOLD.as_posix(): _sha(SOURCE_HOLD),
            SOURCE_HOLD_EVIDENCE.as_posix(): _sha(SOURCE_HOLD_EVIDENCE),
            SOURCE_ADJUDICATION.as_posix(): _sha(SOURCE_ADJUDICATION),
        },
        "implementation_sha256": {
            path.as_posix(): _sha(path) for path in IMPLEMENTATION
        },
        "trajectory": {
            "accepted_source_time_sec": 0.25,
            "nominal_continuation_steps": 3,
            "nominal_step_sec": 0.25,
            "nominal_final_time_sec": 1.0,
            "refinement_start_sec": 0.75,
            "refined_steps": 2,
            "refined_step_sec": 0.125,
        },
        "solver": {
            "method": "least_squares_trf_one_fresh_jacobian_per_root",
            "difference_step": 1.0e-5,
            "expected_color_count": 16,
            "x_scale": 1.0,
            "ftol": 1.0e-11,
            "xtol": 1.0e-11,
            "gtol": 1.0e-11,
            "max_nfev_per_root": 40,
            "acceptance_basis": (
                "residual and physical gates; SciPy termination status is reported"
            ),
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "controller_residual": 1.0e-10,
            "rank": 262,
            "condition": 1.0e8,
            "component_identity_lbmol": 1.0e-6,
            "maximum_step_temperature_F": 0.01,
            "maximum_step_pressure_psia": 0.01,
            "maximum_step_composition": 1.0e-4,
            "maximum_step_flow_relative": 1.0e-3,
            "maximum_step_phase_inventory_relative": 1.0e-3,
            "maximum_step_duty_relative": 1.0e-3,
            "maximum_step_product_relative": 1.0e-3,
            "refinement_component_max_lbmol": 1.0e-5,
            "refinement_component_l1_lbmol": 1.0e-4,
            "refinement_signed_total_lbmol": 1.0e-5,
            "refinement_temperature_F": 1.0e-4,
            "refinement_pressure_psia": 1.0e-4,
            "refinement_flow_relative": 1.0e-4,
            "refinement_phase_transfer_scaled": 1.0e-3,
            "refinement_duty_relative": 1.0e-4,
            "refinement_level_fraction": 1.0e-6,
            "refinement_product_relative": 1.0e-5,
            "logical_provider_calls": 100000,
            "wall_clock_sec": 180.0,
        },
        "energy_identity": {
            "volume_count": 20,
            "energy_residual_scale_BTUph": 54_706_000.0,
            "aggregate_bound_from_scaled_residual": True,
        },
        "hard_stops": [
            "any new endpoint exceeds the residual, rank, condition, physical, or controller limits",
            "drum level or distillate reverses direction while the drum remains below setpoint",
            "sump level or bottoms reverses direction while the sump remains above setpoint",
            "controller memory is discontinuous",
            "component or residual-consistent energy conservation fails",
            "the final nominal and refined endpoints exceed a fixed comparison limit",
            "more than one Jacobian is built in any root",
            "a retry, alternate grid, tuning change, fallback, parallel worker, or extension occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if (ROOT / contract_path).exists() or (ROOT / contract_doc_path).exists():
        raise RuntimeError("DD-267 contract artifact already exists")
    (ROOT / contract_path).write_text(_json_text(payload), encoding="utf-8")
    (ROOT / contract_doc_path).write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    trajectory = payload["trajectory"]
    return "\n".join(
        (
            "# DD-267 Short Controlled Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Source endpoint: `{trajectory['accepted_source_time_sec']} s` from DD-265/DD-266.",
            f"- Nominal continuation: `{trajectory['nominal_continuation_steps']}` x `{trajectory['nominal_step_sec']} s` to `{trajectory['nominal_final_time_sec']} s`.",
            f"- Final refinement: `{trajectory['refined_steps']}` x `{trajectory['refined_step_sec']} s` from `{trajectory['refinement_start_sec']} s`.",
            "- Both PI memories and absolute product-output coordinates continue across every endpoint.",
            "- Each new root receives one fresh 16-color Jacobian held only within that root.",
            "- Residual, physicality, conservation, controller direction, continuity, refinement, provider, call, and wall gates are mandatory.",
            "- Retry, alternate grid, tuning change, fallback, parallel worker, or extension: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-267 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-267 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-267 implementation changed: {path}")
    if any((ROOT / path).exists() for path in (RESULT, EVIDENCE, JOURNAL)):
        raise RuntimeError("DD-267 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _context() -> dict[str, Any]:
    problem = dd248._problem()
    case = load_case_from_excel(str(problem["source"]["workbook"]))
    base_contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
    )
    contract = build_vapor_holdup_terminal_control_contract(
        base_contract,
        geometry=terminal_geometry_from_specs(case.specs),
        controllers=level_controllers_from_specs(case.specs),
    )
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    return {**problem, "contract": contract, "audit": audit, "provider": provider}


def _evaluate(
    context: Mapping[str, Any],
    reference: Any,
    memory_previous: np.ndarray,
    coordinates: np.ndarray,
    timestep_sec: float,
    state_id: str,
    evaluation_kind: str = "jacobian",
):
    return evaluate_vapor_holdup_terminal_control_implicit_residual(
        context["contract"],
        context["geometry"],
        reference,
        context["balance_inputs"],
        context["spec"].hydraulic_geometry,
        replace(context["numerical"], timestep_sec=float(timestep_sec)),
        context["provider"],
        context["audit"],
        coordinates,
        controller_memory_previous=memory_previous,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )


def _physical(evaluation) -> bool:
    endpoint = evaluation.base.endpoint
    return bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.temperature_F > -459.67)
        and np.all(endpoint.pressure_psia > 0.0)
        and np.all(np.diff(endpoint.pressure_psia) >= 0.0)
        and np.all(np.diff(endpoint.temperature_F) >= 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and np.min(evaluation.base.properties.free_volume.free_vapor_volume_ft3)
        > 0.0
        and np.all((evaluation.level_fraction > 0.01) & (evaluation.level_fraction < 0.99))
    )


def _solve_endpoint(
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    reference: Any,
    memory_previous: np.ndarray,
    previous_coordinates: np.ndarray,
    previous_evaluation: Any,
    timestep_sec: float,
    root_name: str,
):
    pattern = vapor_holdup_terminal_control_pattern(context["contract"])
    lower, upper = dd265._bounds(context["contract"])
    point = controlled_implicit_initial_coordinates(
        context["contract"],
        controller_rates_per_sec=previous_evaluation.controller_rate_per_sec,
        timestep_sec=timestep_sec,
        previous_coordinates=previous_coordinates,
        product_log_ratios_previous=previous_evaluation.product_log_ratio,
    )
    cached_matrix: np.ndarray | None = None
    groups_used = 0
    function_calls = 0

    def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
        nonlocal function_calls
        function_calls += 1
        return _evaluate(
            context,
            reference,
            memory_previous,
            candidate,
            timestep_sec,
            f"{root_name}:{state_id}:{function_calls}",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal cached_matrix, groups_used
        if cached_matrix is None:
            cached_matrix, groups = colored_central_difference_jacobian(
                objective,
                candidate,
                pattern=pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=f"{root_name}:jacobian",
            )
            groups_used = len(groups)
        return cached_matrix

    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=float(payload["solver"]["x_scale"]),
        ftol=float(payload["solver"]["ftol"]),
        xtol=float(payload["solver"]["xtol"]),
        gtol=float(payload["solver"]["gtol"]),
        max_nfev=int(payload["solver"]["max_nfev_per_root"]),
        verbose=0,
    )
    final = _evaluate(
        context,
        reference,
        memory_previous,
        solution.x,
        timestep_sec,
        f"{root_name}:accepted",
        "residual",
    )
    if cached_matrix is None:
        raise RuntimeError("DD-267 root did not build its required Jacobian")
    rank, condition, _singular = dd249._rank_condition(cached_matrix)
    memory_error = float(
        np.max(
            np.abs(
                final.controller_memory_endpoint
                - memory_previous
                - timestep_sec * final.controller_rate_per_sec
            )
        )
    )
    report = {
        "scipy_success": bool(solution.success),
        "scipy_status": int(solution.status),
        "scipy_message": str(solution.message),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "function_calls_observed": function_calls,
        "jacobian_build_count": 1,
        "color_count": groups_used,
        "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
        "controller_residual_inf_norm": float(np.max(np.abs(final.scaled[-4:]))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "physical_pass": _physical(final),
        "controller_memory_recurrence_error": memory_error,
        "level_fraction": final.level_fraction.tolist(),
        "controller_memory_endpoint": final.controller_memory_endpoint.tolist(),
        "controller_rate_per_sec": final.controller_rate_per_sec.tolist(),
        "product_log_ratio": final.product_log_ratio.tolist(),
        "distillate_lbmolph": final.distillate_lbmolph,
        "bottoms_lbmolph": final.bottoms_lbmolph,
    }
    return solution.x.copy(), final, report, cached_matrix


def _compositions(inventory: np.ndarray) -> np.ndarray:
    return inventory / np.sum(inventory, axis=1, keepdims=True)


def _relative_max(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.max(np.abs(left - right) / np.maximum(np.abs(right), 1.0)))


def _continuity(reference: Any, evaluations: list[Any], products: np.ndarray) -> dict[str, float]:
    maxima = {
        "temperature_F": 0.0,
        "pressure_psia": 0.0,
        "composition": 0.0,
        "flow_relative": 0.0,
        "phase_inventory_relative": 0.0,
        "duty_relative": 0.0,
        "product_relative": 0.0,
    }
    prior_t = reference.temperature_F
    prior_p = reference.pressure_psia
    prior_l = reference.hydraulic_liquid_flow_lbmolph
    prior_v = reference.vapor_flow_lbmolph
    prior_nl = reference.liquid_component_inventory_lbmol
    prior_nv = reference.vapor_component_inventory_lbmol
    prior_q = reference.condenser_duty_BTUph
    prior_products = products.copy()
    for evaluation in evaluations:
        endpoint = evaluation.base.endpoint
        current_products = np.asarray(
            (evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph)
        )
        maxima["temperature_F"] = max(
            maxima["temperature_F"],
            float(np.max(np.abs(endpoint.temperature_F - prior_t))),
        )
        maxima["pressure_psia"] = max(
            maxima["pressure_psia"],
            float(np.max(np.abs(endpoint.pressure_psia - prior_p))),
        )
        maxima["composition"] = max(
            maxima["composition"],
            float(np.max(np.abs(_compositions(endpoint.liquid_component_inventory_lbmol) - _compositions(prior_nl)))),
            float(np.max(np.abs(_compositions(endpoint.vapor_component_inventory_lbmol) - _compositions(prior_nv)))),
        )
        maxima["flow_relative"] = max(
            maxima["flow_relative"],
            _relative_max(endpoint.hydraulic_liquid_flow_lbmolph, prior_l),
            _relative_max(endpoint.vapor_flow_lbmolph, prior_v),
        )
        maxima["phase_inventory_relative"] = max(
            maxima["phase_inventory_relative"],
            _relative_max(endpoint.liquid_component_inventory_lbmol, prior_nl),
            _relative_max(endpoint.vapor_component_inventory_lbmol, prior_nv),
        )
        maxima["duty_relative"] = max(
            maxima["duty_relative"],
            abs(endpoint.condenser_duty_BTUph - prior_q) / abs(prior_q),
        )
        maxima["product_relative"] = max(
            maxima["product_relative"],
            _relative_max(current_products, prior_products),
        )
        prior_t = endpoint.temperature_F
        prior_p = endpoint.pressure_psia
        prior_l = endpoint.hydraulic_liquid_flow_lbmolph
        prior_v = endpoint.vapor_flow_lbmolph
        prior_nl = endpoint.liquid_component_inventory_lbmol
        prior_nv = endpoint.vapor_component_inventory_lbmol
        prior_q = endpoint.condenser_duty_BTUph
        prior_products = current_products
    return maxima


def _response(initial: Any, evaluations: list[Any], durations: list[float]) -> dict[str, Any]:
    final = evaluations[-1].base
    actual_component = np.sum(
        final.endpoint.liquid_component_inventory_lbmol
        + final.endpoint.vapor_component_inventory_lbmol
        - initial.liquid_component_inventory_lbmol
        - initial.vapor_component_inventory_lbmol,
        axis=0,
    )
    expected_component = sum(
        evaluation.base.transport.external_component_rate_lbmolph
        * (duration / 3600.0)
        for evaluation, duration in zip(evaluations, durations, strict=True)
    )
    actual_energy = float(
        np.sum(final.properties.total_stored_energy_BTU - initial.total_stored_energy_BTU)
    )
    expected_energy = float(
        sum(
            evaluation.base.transport.external_energy_rate_BTUph
            * (duration / 3600.0)
            for evaluation, duration in zip(evaluations, durations, strict=True)
        )
    )
    return {
        "actual_component_change_lbmol": actual_component.tolist(),
        "expected_component_change_lbmol": expected_component.tolist(),
        "component_identity_max_abs_lbmol": float(
            np.max(np.abs(actual_component - expected_component))
        ),
        "actual_energy_change_BTU": actual_energy,
        "expected_energy_change_BTU": expected_energy,
        "energy_identity_absolute_BTU": abs(actual_energy - expected_energy),
    }


def _refinement(nominal: Any, refined: Any, initial: Any) -> dict[str, float]:
    left = nominal.base.endpoint
    right = refined.base.endpoint
    left_total = left.liquid_component_inventory_lbmol + left.vapor_component_inventory_lbmol
    right_total = right.liquid_component_inventory_lbmol + right.vapor_component_inventory_lbmol
    delta = left_total - right_total
    left_products = np.asarray((nominal.distillate_lbmolph, nominal.bottoms_lbmolph))
    right_products = np.asarray((refined.distillate_lbmolph, refined.bottoms_lbmolph))
    return {
        "component_max_lbmol": float(np.max(np.abs(delta))),
        "component_l1_lbmol": float(np.sum(np.abs(delta))),
        "signed_total_lbmol": float(abs(np.sum(delta))),
        "temperature_F": float(np.max(np.abs(left.temperature_F - right.temperature_F))),
        "pressure_psia": float(np.max(np.abs(left.pressure_psia - right.pressure_psia))),
        "flow_relative": max(
            _relative_max(left.hydraulic_liquid_flow_lbmolph, right.hydraulic_liquid_flow_lbmolph),
            _relative_max(left.vapor_flow_lbmolph, right.vapor_flow_lbmolph),
        ),
        "phase_transfer_scaled": float(
            np.max(
                np.abs(left.phase_transfer_lbmolph - right.phase_transfer_lbmolph)
                / initial.phase_transfer_scale_lbmolph
            )
        ),
        "duty_relative": abs(left.condenser_duty_BTUph - right.condenser_duty_BTUph)
        / abs(right.condenser_duty_BTUph),
        "level_fraction": float(
            np.max(np.abs(nominal.level_fraction - refined.level_fraction))
        ),
        "product_relative": _relative_max(left_products, right_products),
    }


def _profile(context: Mapping[str, Any], evaluation: Any) -> list[dict[str, Any]]:
    topology = context["contract"].base.topology.column
    endpoint = evaluation.base.endpoint
    liquid_x = _compositions(endpoint.liquid_component_inventory_lbmol)
    vapor_y = _compositions(endpoint.vapor_component_inventory_lbmol)
    liquid_flow = dict(
        zip(topology.hydraulic_volume_ids, endpoint.hydraulic_liquid_flow_lbmolph, strict=True)
    )
    vapor_flow = {
        source: float(endpoint.vapor_flow_lbmolph[index])
        for index, (source, _destination, _name) in enumerate(topology.vapor_links)
    }
    return [
        {
            "volume": volume,
            "temperature_F": float(endpoint.temperature_F[index]),
            "pressure_psia": float(endpoint.pressure_psia[index]),
            "liquid_inventory_lbmol": float(np.sum(endpoint.liquid_component_inventory_lbmol[index])),
            "vapor_inventory_lbmol": float(np.sum(endpoint.vapor_component_inventory_lbmol[index])),
            "liquid_flow_lbmolph": (
                None if volume not in liquid_flow else float(liquid_flow[volume])
            ),
            "vapor_flow_lbmolph": vapor_flow.get(volume),
            "liquid_mole_fraction": liquid_x[index].tolist(),
            "vapor_mole_fraction": vapor_y[index].tolist(),
        }
        for index, volume in enumerate(topology.volume_ids)
    ]


def _journal(index: str, time_sec: float, report: Mapping[str, Any], coordinates: np.ndarray) -> None:
    destination = ROOT / JOURNAL / f"endpoint_{index}.json"
    if destination.exists():
        raise RuntimeError(f"DD-267 journal collision: {destination}")
    destination.write_text(
        _json_text(
            {
                "schema_id": "dd267-controlled-endpoint-journal-v1",
                "index": index,
                "time_sec": time_sec,
                "report": report,
                "coordinates": coordinates.tolist(),
            }
        ),
        encoding="utf-8",
    )


def execute(contract_path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path)
    context = _context()
    hold = json.loads((ROOT / SOURCE_HOLD).read_text(encoding="utf-8"))
    source_coordinates = np.load(ROOT / SOURCE_HOLD_EVIDENCE)["endpoint_coordinates"]
    memory_initial = np.asarray(
        hold["terminal"]["controller_memory_previous"], dtype=float
    )
    source = _evaluate(
        context,
        context["reference"],
        memory_initial,
        source_coordinates,
        0.25,
        "dd267:source_parity",
        "residual",
    )
    if (
        abs(source.distillate_lbmolph - hold["terminal"]["endpoint_product_lbmolph"][0])
        > 1.0e-10
        or abs(source.bottoms_lbmolph - hold["terminal"]["endpoint_product_lbmolph"][1])
        > 1.0e-10
    ):
        raise RuntimeError("DD-267 source endpoint parity failed")
    (ROOT / JOURNAL).mkdir(parents=True, exist_ok=False)
    initial_reference = context["reference"]
    initial_products = np.asarray(
        (
            float(context["balance_inputs"].distillate_lbmolph),
            float(context["balance_inputs"].bottoms_lbmolph),
        )
    )
    reference = dd249._next_reference(context["reference"], source.base)
    memory = source.controller_memory_endpoint.copy()
    coordinates = source_coordinates.copy()
    prior = source
    nominal_evaluations = [source]
    nominal_coordinates = [source_coordinates.copy()]
    nominal_memories = [memory.copy()]
    nominal_reports = [
        {
            "index": 1,
            "time_sec": 0.25,
            "source_from_dd265_dd266": True,
            "scaled_residual_inf_norm": float(np.max(np.abs(source.scaled))),
            "level_fraction": source.level_fraction.tolist(),
            "distillate_lbmolph": source.distillate_lbmolph,
            "bottoms_lbmolph": source.bottoms_lbmolph,
        }
    ]
    matrices: list[np.ndarray] = []
    branch = None
    started = time.perf_counter()
    for index in range(2, 5):
        coordinates, final, report, matrix = _solve_endpoint(
            context,
            payload,
            reference,
            memory,
            coordinates,
            prior,
            0.25,
            f"dd267:nominal_{index}",
        )
        report.update({"index": index, "time_sec": index * 0.25})
        _journal(f"nominal_{index}", index * 0.25, report, coordinates)
        nominal_evaluations.append(final)
        nominal_coordinates.append(coordinates.copy())
        nominal_memories.append(final.controller_memory_endpoint.copy())
        nominal_reports.append(report)
        matrices.append(matrix)
        reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
        prior = final
        if index == 3:
            branch = (reference, memory.copy(), coordinates.copy(), final)
    if branch is None:
        raise RuntimeError("DD-267 refinement branch was not captured")
    refined_reference, refined_memory, refined_coordinates, refined_prior = branch
    refined_evaluations: list[Any] = []
    refined_reports: list[dict[str, Any]] = []
    refined_coordinate_rows: list[np.ndarray] = []
    refined_memory_rows: list[np.ndarray] = []
    for index in range(1, 3):
        refined_coordinates, final, report, matrix = _solve_endpoint(
            context,
            payload,
            refined_reference,
            refined_memory,
            refined_coordinates,
            refined_prior,
            0.125,
            f"dd267:refined_{index}",
        )
        time_sec = 0.75 + index * 0.125
        report.update({"index": index, "time_sec": time_sec})
        _journal(f"refined_{index}", time_sec, report, refined_coordinates)
        refined_evaluations.append(final)
        refined_reports.append(report)
        refined_coordinate_rows.append(refined_coordinates.copy())
        refined_memory_rows.append(final.controller_memory_endpoint.copy())
        matrices.append(matrix)
        refined_reference = dd249._next_reference(refined_reference, final.base)
        refined_memory = final.controller_memory_endpoint.copy()
        refined_prior = final
    wall = time.perf_counter() - started
    nominal_response = _response(
        initial_reference, nominal_evaluations, [0.25] * 4
    )
    refined_path = [
        nominal_evaluations[0],
        nominal_evaluations[1],
        nominal_evaluations[2],
        *refined_evaluations,
    ]
    refined_response = _response(
        initial_reference, refined_path, [0.25, 0.25, 0.25, 0.125, 0.125]
    )
    continuity = _continuity(
        initial_reference, nominal_evaluations, initial_products
    )
    refinement = _refinement(
        nominal_evaluations[-1], refined_evaluations[-1], initial_reference
    )
    levels = np.asarray(
        [evaluation.level_fraction for evaluation in nominal_evaluations]
    )
    products = np.asarray(
        [
            (evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph)
            for evaluation in nominal_evaluations
        ]
    )
    new_reports = [*nominal_reports[1:], *refined_reports]
    limits = payload["limits"]
    total_duration = sum([0.25] * 4)
    energy_bound = (
        int(payload["energy_identity"]["volume_count"])
        * float(limits["scaled_residual"])
        * float(payload["energy_identity"]["energy_residual_scale_BTUph"])
        * total_duration
        / 3600.0
    )
    endpoint_gate = all(
        report["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and report["controller_residual_inf_norm"] < limits["controller_residual"]
        and report["jacobian_rank"] == limits["rank"]
        and report["jacobian_condition"] < limits["condition"]
        and report["physical_pass"]
        and report["controller_memory_recurrence_error"] < 1.0e-14
        and report["jacobian_build_count"] == 1
        and report["color_count"] == payload["solver"]["expected_color_count"]
        for report in new_reports
    )
    gates = {
        "source_parity": True,
        "new_endpoints": endpoint_gate,
        "nominal_complete": len(nominal_evaluations) == 4,
        "refinement_complete": len(refined_evaluations) == 2,
        "drum_level_monotonic_toward_setpoint": bool(np.all(np.diff(levels[:, 0]) > 0.0)),
        "sump_level_monotonic_toward_setpoint": bool(np.all(np.diff(levels[:, 1]) < 0.0)),
        "distillate_monotonic": bool(np.all(np.diff(products[:, 0]) < 0.0)),
        "bottoms_monotonic": bool(np.all(np.diff(products[:, 1]) > 0.0)),
        "component_identity_nominal": nominal_response["component_identity_max_abs_lbmol"]
        < limits["component_identity_lbmol"],
        "component_identity_refined": refined_response["component_identity_max_abs_lbmol"]
        < limits["component_identity_lbmol"],
        "energy_identity_nominal": nominal_response["energy_identity_absolute_BTU"]
        < energy_bound,
        "energy_identity_refined": refined_response["energy_identity_absolute_BTU"]
        < energy_bound,
        "continuity": bool(
            continuity["temperature_F"] < limits["maximum_step_temperature_F"]
            and continuity["pressure_psia"] < limits["maximum_step_pressure_psia"]
            and continuity["composition"] < limits["maximum_step_composition"]
            and continuity["flow_relative"] < limits["maximum_step_flow_relative"]
            and continuity["phase_inventory_relative"]
            < limits["maximum_step_phase_inventory_relative"]
            and continuity["duty_relative"] < limits["maximum_step_duty_relative"]
            and continuity["product_relative"] < limits["maximum_step_product_relative"]
        ),
        "refinement": bool(
            refinement["component_max_lbmol"] < limits["refinement_component_max_lbmol"]
            and refinement["component_l1_lbmol"] < limits["refinement_component_l1_lbmol"]
            and refinement["signed_total_lbmol"] < limits["refinement_signed_total_lbmol"]
            and refinement["temperature_F"] < limits["refinement_temperature_F"]
            and refinement["pressure_psia"] < limits["refinement_pressure_psia"]
            and refinement["flow_relative"] < limits["refinement_flow_relative"]
            and refinement["phase_transfer_scaled"]
            < limits["refinement_phase_transfer_scaled"]
            and refinement["duty_relative"] < limits["refinement_duty_relative"]
            and refinement["level_fraction"] < limits["refinement_level_fraction"]
            and refinement["product_relative"] < limits["refinement_product_relative"]
        ),
        "provider": bool(
            context["audit"].report()["pass"]
            and not context["audit"].fallback_attempted
        ),
        "calls": context["audit"].record_count < limits["logical_provider_calls"],
        "wall": wall < limits["wall_clock_sec"],
        "one_fresh_jacobian_per_new_root": len(matrices) == 5,
        "no_retry_or_alternate": True,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_terminal_control_short_trajectory_passed"
            if passed
            else "vapor_holdup_terminal_control_short_trajectory_failed"
        ),
        "decision": (
            "authorize_separately_frozen_longer_controlled_trajectory_contract"
            if passed
            else "stop_controlled_trajectory_extension"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "nominal_endpoints": nominal_reports,
        "refined_endpoints": refined_reports,
        "nominal_response": nominal_response,
        "refined_response": refined_response,
        "energy_identity_bound_BTU": energy_bound,
        "continuity": continuity,
        "refinement": refinement,
        "final_profile": _profile(context, nominal_evaluations[-1]),
        "component_names": list(context["contract"].base.component_names),
        "provider": compact_provider_report(context["audit"].report()),
        "logical_provider_calls": context["audit"].record_count,
        "wall_clock_sec": wall,
        "simulation_wall_ratio": 0.75 / max(wall, 1.0e-300),
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "tuning_change_attempted": False,
        "parallel_worker_attempted": False,
        "longer_trajectory_attempted": False,
    }
    (ROOT / RESULT).write_text(_json_text(report), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        ROOT / EVIDENCE,
        nominal_coordinates=np.stack(nominal_coordinates),
        nominal_controller_memory=np.stack(nominal_memories),
        refined_coordinates=np.stack(refined_coordinate_rows),
        refined_controller_memory=np.stack(refined_memory_rows),
        **{f"jacobian_new_root_{index}": matrix for index, matrix in enumerate(matrices, 1)},
    )
    return report


def _result_markdown(report: Mapping[str, Any]) -> str:
    final = report["nominal_endpoints"][-1]
    return "\n".join(
        (
            "# DD-267 Short Controlled Trajectory Result",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Nominal endpoints: `{len(report['nominal_endpoints'])}` through `1.0 s`",
            f"- Final refinement endpoints: `{len(report['refined_endpoints'])}`",
            f"- Final drum/sump levels: `{final['level_fraction']}`",
            f"- Final D/B: `{final['distillate_lbmolph']:.6f} / {final['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Worst continuity: `{report['continuity']}`",
            f"- Final-step refinement: `{report['refinement']}`",
            f"- Provider calls: `{report['logical_provider_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            f"- Gates: `{report['gates']}`",
            "- Retry, alternate grid, tuning change, parallel worker, or extension: `False`",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
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
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "failed_gates": [
                    key for key, value in report["gates"].items() if not value
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
