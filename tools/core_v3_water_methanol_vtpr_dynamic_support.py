"""Shared numerical support for the water-methanol Core V3 dynamic audits."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_specification_aware_root as reconciled_root  # noqa: E402
from run_core_v3_water_methanol_stationary_root import compact_provider_report  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.end_of_run_summary_v1 import (  # noqa: E402
    build_end_of_run_summary,
    format_end_of_run_summary,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.stationary_specification_ownership_v1 import (  # noqa: E402
    fixed_bottoms_solved_reboiler_trial,
)
from dynamic_distillation.core_v3.total_reboiler_implicit_v1 import (  # noqa: E402
    apply_total_reboiler_implicit_boundary,
    total_reboiler_implicit_structural_pattern,
)
from dynamic_distillation.core_v3.total_reboiler_stationary_v1 import (  # noqa: E402
    apply_total_reboiler_boundary,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    decode_vapor_holdup_endpoint,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_step_bounds_v1 import (  # noqa: E402
    vapor_holdup_implicit_step_coordinate_bounds,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    terminal_geometry_from_specs,
)


SOURCE_ROOT = Path(
    "logs/core_v3_water_methanol_vtpr_phase_total_stationary_root_20260831.json"
)
SOURCE_PULSE = Path(
    "logs/core_v3_water_methanol_vtpr_feed_pulse_trajectory_20260831.json"
)
SOURCE_PULSE_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_feed_pulse_trajectory_20260831.npz"
)
SOURCE_RECONCILED_HYDRAULIC_ROOT = Path(
    "logs/core_v3_water_methanol_design_calibrated_hydraulic_root_20260901.json"
)
SOURCE_RECONCILED_HYDRAULIC_MATRIX = Path(
    "logs/core_v3_water_methanol_design_calibrated_hydraulic_root_20260901.npz"
)
SOURCE_PARTIAL_HYDRAULIC_ROOT = Path(
    "logs/core_v3_water_methanol_partial_hydraulic_root_20260901.json"
)
SOURCE_PARTIAL_HYDRAULIC_MATRIX = Path(
    "logs/core_v3_water_methanol_partial_hydraulic_root_20260901.npz"
)

DIFFERENCE_STEP = 1.0e-5
RESIDUAL_LIMIT = 1.0e-8
COMPONENT_IDENTITY_LIMIT_LBMOL = 1.0e-6
ENERGY_IDENTITY_RELATIVE_LIMIT = 1.0e-8
ENERGY_IDENTITY_ABSOLUTE_LIMIT_BTU = 1.0e-5
MAX_NFEV = 20


@dataclass
class DynamicCase:
    problem: dict[str, Any]
    provider: Any
    contract: Any
    base_inputs: Any
    post_pulse_reference: VaporHoldupImplicitReference
    pattern: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    coordinate_scale: np.ndarray
    phase_scale_floor: np.ndarray
    source_reports: dict[str, Any]
    history_provider_report: dict[str, Any]
    history_provider_calls: int
    residual_transform: Callable[[Any, VaporHoldupImplicitNumericalSpec], Any] | None = None


@dataclass
class SolvedStep:
    solution: Any
    evaluation: Any
    numerical: VaporHoldupImplicitNumericalSpec
    reference: VaporHoldupImplicitReference
    metrics: dict[str, Any]
    gates: dict[str, bool]
    provider_report: dict[str, Any]
    provider_calls: int
    objective: Callable[[np.ndarray, str], np.ndarray]
    audit: ProviderCallAudit


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30)
    return float(np.linalg.norm(left - right) / denominator)


def rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def numerical_spec(
    problem: dict[str, Any], *, timestep_sec: float, top_pressure_psia: float
) -> VaporHoldupImplicitNumericalSpec:
    source = problem["numerical"]
    return VaporHoldupImplicitNumericalSpec(
        timestep_sec=float(timestep_sec),
        temperature_coordinate_scale_F=source.temperature_coordinate_scale_F,
        pressure_coordinate_scale_psia=source.pressure_coordinate_scale_psia,
        dry_tray_pressure_drop_coefficient=source.dry_tray_pressure_drop_coefficient,
        component_mw_lbm_per_lbmol=source.component_mw_lbm_per_lbmol,
        pressure_link_geometry=source.pressure_link_geometry,
        top_pressure_anchor_psia=float(top_pressure_psia),
        component_residual_scale_lbmolph=source.component_residual_scale_lbmolph,
        energy_residual_scale_BTUph=source.energy_residual_scale_BTUph,
        pressure_residual_scale_psia=source.pressure_residual_scale_psia,
    )


def next_reference(
    case: DynamicCase,
    evaluation: Any,
) -> VaporHoldupImplicitReference:
    endpoint = evaluation.endpoint
    return VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=(
            endpoint.liquid_component_inventory_lbmol.copy()
        ),
        vapor_component_inventory_lbmol=(
            endpoint.vapor_component_inventory_lbmol.copy()
        ),
        phase_transfer_lbmolph=endpoint.phase_transfer_lbmolph.copy(),
        phase_transfer_scale_lbmolph=np.maximum(
            np.abs(endpoint.phase_transfer_lbmolph), case.phase_scale_floor
        ),
        temperature_F=endpoint.temperature_F.copy(),
        pressure_psia=endpoint.pressure_psia.copy(),
        hydraulic_liquid_flow_lbmolph=(
            endpoint.hydraulic_liquid_flow_lbmolph.copy()
        ),
        vapor_flow_lbmolph=endpoint.vapor_flow_lbmolph.copy(),
        condenser_duty_BTUph=float(endpoint.condenser_duty_BTUph),
        total_stored_energy_BTU=evaluation.properties.total_stored_energy_BTU.copy(),
    )


def _coordinate_scale(matrix_path: Path, dimension: int) -> np.ndarray:
    with np.load(matrix_path) as evidence:
        matrix = np.asarray(evidence["jacobian_h1"], dtype=float)
    norms = np.linalg.norm(matrix, axis=0)
    scale = 1.0 / np.maximum(norms, 1.0e-30)
    scale /= np.median(scale)
    if scale.shape != (dimension,) or np.any(~np.isfinite(scale)) or np.any(scale <= 0.0):
        raise RuntimeError("pulse endpoint Jacobian produced an invalid coordinate scale")
    return scale


def _physical(evaluation: Any) -> bool:
    endpoint = evaluation.endpoint
    return bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.temperature_F > -459.67)
        and np.all(endpoint.pressure_psia > 0.0)
        and np.all(np.diff(endpoint.pressure_psia) > 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and np.min(evaluation.properties.free_volume.free_vapor_volume_ft3) > 0.0
    )


def load_post_pulse_case() -> DynamicCase:
    root_path = rooted(SOURCE_ROOT).resolve()
    pulse_path = rooted(SOURCE_PULSE).resolve()
    pulse_matrix_path = rooted(SOURCE_PULSE_MATRIX).resolve()
    root = json.loads(root_path.read_text(encoding="utf-8"))
    pulse = json.loads(pulse_path.read_text(encoding="utf-8"))
    if (
        not root.get("pass_gate")
        or not pulse.get("pass_gate")
        or not pulse.get("feed_disturbance_removed")
        or pulse.get("restoration", {}).get("disturbance_active_at_end")
        or pulse.get("component_specific_logic") is not False
    ):
        raise RuntimeError("post-pulse case requires accepted evidence and nominal feed")

    problem = starting_state.build_problem(density_model=root["density_model"])
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    endpoint = root["endpoint"]
    contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
        product_flow_parameters=("D_stationary_root", "B_stationary_root"),
    )
    phase_scale_floor = np.asarray(
        problem["numerical"].component_residual_scale_lbmolph, dtype=float
    )
    history_audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    initial_properties = evaluate_vapor_holdup_trial_properties(
        problem["geometry"],
        np.asarray(endpoint["liquid_component_inventory_lbmol"], dtype=float),
        np.asarray(endpoint["vapor_component_inventory_lbmol"], dtype=float),
        np.asarray(endpoint["temperature_F"], dtype=float),
        np.asarray(endpoint["pressure_psia"], dtype=float),
        provider,
        history_audit,
        state_id="water_methanol:dynamic_support:root_energy",
        evaluation_kind="residual",
    )
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=np.asarray(
            endpoint["liquid_component_inventory_lbmol"], dtype=float
        ),
        vapor_component_inventory_lbmol=np.asarray(
            endpoint["vapor_component_inventory_lbmol"], dtype=float
        ),
        phase_transfer_lbmolph=np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float),
        phase_transfer_scale_lbmolph=np.maximum(
            np.abs(np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)),
            phase_scale_floor,
        ),
        temperature_F=np.asarray(endpoint["temperature_F"], dtype=float),
        pressure_psia=np.asarray(endpoint["pressure_psia"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
        total_stored_energy_BTU=initial_properties.total_stored_energy_BTU,
    )
    history_numerical = numerical_spec(
        problem,
        timestep_sec=float(pulse["timestep_sec"]),
        top_pressure_psia=float(reference.pressure_psia[0]),
    )
    with np.load(pulse_matrix_path) as evidence:
        coordinates = np.asarray(evidence["coordinates"], dtype=float)
    for point in coordinates:
        reconstructed = decode_vapor_holdup_endpoint(
            contract, reference, history_numerical, point
        )
        reference = replace(
            reference,
            liquid_component_inventory_lbmol=(
                reconstructed.liquid_component_inventory_lbmol.copy()
            ),
            vapor_component_inventory_lbmol=(
                reconstructed.vapor_component_inventory_lbmol.copy()
            ),
            phase_transfer_lbmolph=reconstructed.phase_transfer_lbmolph.copy(),
            phase_transfer_scale_lbmolph=np.maximum(
                np.abs(reconstructed.phase_transfer_lbmolph), phase_scale_floor
            ),
            temperature_F=reconstructed.temperature_F.copy(),
            pressure_psia=reconstructed.pressure_psia.copy(),
            hydraulic_liquid_flow_lbmolph=(
                reconstructed.hydraulic_liquid_flow_lbmolph.copy()
            ),
            vapor_flow_lbmolph=reconstructed.vapor_flow_lbmolph.copy(),
            condenser_duty_BTUph=float(reconstructed.condenser_duty_BTUph),
        )
    final_properties = evaluate_vapor_holdup_trial_properties(
        problem["geometry"],
        reference.liquid_component_inventory_lbmol,
        reference.vapor_component_inventory_lbmol,
        reference.temperature_F,
        reference.pressure_psia,
        provider,
        history_audit,
        state_id="water_methanol:dynamic_support:post_pulse_energy",
        evaluation_kind="residual",
    )
    reference = replace(
        reference,
        total_stored_energy_BTU=final_properties.total_stored_energy_BTU.copy(),
    )
    base_inputs = replace(
        problem["balance_inputs"],
        distillate_lbmolph=float(endpoint["distillate_lbmolph"]),
        bottoms_lbmolph=float(endpoint["bottoms_lbmolph"]),
        condenser_duty_BTUph=float(reference.condenser_duty_BTUph),
    )
    dimension = len(contract.rows)
    lower, upper = vapor_holdup_implicit_step_coordinate_bounds(contract)
    return DynamicCase(
        problem=problem,
        provider=provider,
        contract=contract,
        base_inputs=base_inputs,
        post_pulse_reference=reference,
        pattern=vapor_holdup_structural_pattern(contract),
        lower=lower,
        upper=upper,
        coordinate_scale=_coordinate_scale(pulse_matrix_path, dimension),
        phase_scale_floor=phase_scale_floor,
        source_reports={"root": root, "pulse": pulse},
        history_provider_report=compact_provider_report(history_audit.report()),
        history_provider_calls=history_audit.record_count,
    )


def _load_hydraulic_case(
    *, report_source: Path, matrix_source: Path, expected_reboiler_type: str
) -> DynamicCase:
    """Rebuild an accepted hydraulic root as a dynamic checkpoint."""
    if expected_reboiler_type not in {"partial", "total"}:
        raise ValueError("hydraulic checkpoint reboiler type is invalid")
    report_path = rooted(report_source).resolve()
    matrix_path = rooted(matrix_source).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        not report.get("pass_gate")
        or report.get("pressure_mode") != "hydraulic_free"
        or report.get("reboiler_type") != expected_reboiler_type
        or not report.get("fugacity_calibration", {}).get("enabled")
        or not report.get("enthalpy_calibration", {}).get("enabled")
    ):
        raise RuntimeError("dynamic checkpoint requires the accepted reconciled root")

    problem = starting_state.build_problem(
        density_model="VTPR",
        property_package="unifac",
    )
    provider, _fugacity_report = reconciled_root._chemsep_profile_calibration(
        problem,
        pressure_psia=14.6959,
        degree=int(report["fugacity_calibration"]["requested_degree"]),
    )
    problem["provider"] = provider
    provider, _enthalpy_report = reconciled_root._chemsep_enthalpy_calibration(
        problem,
        pressure_psia=14.6959,
        degree=int(report["enthalpy_calibration"]["requested_degree"]),
    )
    problem["provider"] = provider
    problem["provider_audit_kwargs"]["provider_identity"] = (
        "dwsim_chemsep_profile_enthalpy_calibrated"
    )
    source = problem["source"]
    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_total = float(np.sum(feed_component))
    feed_enthalpy = provider.phase_enthalpy_BTU_lbmol(
        "liquid",
        float(source["feed_temperature_F"]),
        14.6959,
        feed_component / feed_total,
    )
    problem["balance_inputs"] = replace(
        problem["balance_inputs"],
        feed_enthalpy_BTUph=feed_total * float(feed_enthalpy),
    )
    problem["numerical"] = replace(
        problem["numerical"],
        dry_tray_pressure_drop_coefficient=float(
            report["pressure_hydraulics"]["dry_tray_pressure_drop_coefficient"]
        ),
    )
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    with np.load(matrix_path, allow_pickle=False) as saved:
        coordinates = np.asarray(saved["coordinates"], dtype=float)
    stationary_contract = problem["contract"]
    fixed_bottoms = float(report["specification_ownership"]["bottoms_lbmolph"])
    trial = fixed_bottoms_solved_reboiler_trial(
        stationary_contract,
        problem["reference"],
        problem["balance_inputs"],
        coordinates,
        fixed_bottoms_lbmolph=fixed_bottoms,
    )
    history_audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    stationary = evaluate_vapor_holdup_stationary_residual(
        stationary_contract,
        problem["geometry"],
        problem["reference"],
        trial.balance_inputs,
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        provider,
        history_audit,
        trial.base_coordinates,
        state_id="water_methanol:dynamic_support:reconciled_hydraulic_root",
        evaluation_kind="residual",
    )
    if expected_reboiler_type == "total":
        stationary = apply_total_reboiler_boundary(
            stationary_contract,
            stationary,
            temperature_scale_F=problem["numerical"].temperature_coordinate_scale_F,
        )
    if float(np.max(np.abs(stationary.scaled))) >= RESIDUAL_LIMIT:
        raise RuntimeError("reconstructed hydraulic root no longer closes")
    endpoint = stationary.endpoint
    contract = build_vapor_holdup_dae_contract(
        stationary_contract.component_names,
        topology=stationary_contract.topology,
        product_flow_parameters=("D_hydraulic_root", "B_hydraulic_root"),
    )
    phase_scale_floor = np.asarray(
        problem["numerical"].component_residual_scale_lbmolph, dtype=float
    )
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=(
            endpoint.liquid_component_inventory_lbmol.copy()
        ),
        vapor_component_inventory_lbmol=(
            endpoint.vapor_component_inventory_lbmol.copy()
        ),
        phase_transfer_lbmolph=endpoint.phase_transfer_lbmolph.copy(),
        phase_transfer_scale_lbmolph=np.maximum(
            np.abs(endpoint.phase_transfer_lbmolph), phase_scale_floor
        ),
        temperature_F=endpoint.temperature_F.copy(),
        pressure_psia=endpoint.pressure_psia.copy(),
        hydraulic_liquid_flow_lbmolph=(
            endpoint.hydraulic_liquid_flow_lbmolph.copy()
        ),
        vapor_flow_lbmolph=endpoint.vapor_flow_lbmolph.copy(),
        condenser_duty_BTUph=float(endpoint.condenser_duty_BTUph),
        total_stored_energy_BTU=(
            stationary.properties.total_stored_energy_BTU.copy()
        ),
    )
    base_inputs = replace(
        trial.balance_inputs,
        distillate_lbmolph=float(endpoint.distillate_lbmolph),
        bottoms_lbmolph=float(endpoint.bottoms_lbmolph),
        condenser_duty_BTUph=float(endpoint.condenser_duty_BTUph),
        reboiler_duty_BTUph=float(trial.reboiler_duty_BTUph),
    )
    lower, upper = vapor_holdup_implicit_step_coordinate_bounds(contract)

    residual_transform = None
    pattern = vapor_holdup_structural_pattern(contract)
    if expected_reboiler_type == "total":
        def transform(
            evaluation: Any, numerical: VaporHoldupImplicitNumericalSpec
        ) -> Any:
            return apply_total_reboiler_implicit_boundary(
                contract,
                evaluation,
                temperature_scale_F=numerical.temperature_coordinate_scale_F,
            )

        residual_transform = transform
        pattern = total_reboiler_implicit_structural_pattern(contract)

    return DynamicCase(
        problem=problem,
        provider=provider,
        contract=contract,
        base_inputs=base_inputs,
        post_pulse_reference=reference,
        pattern=pattern,
        lower=lower,
        upper=upper,
        coordinate_scale=np.ones(len(contract.rows), dtype=float),
        phase_scale_floor=phase_scale_floor,
        source_reports={f"{expected_reboiler_type}_hydraulic_root": report},
        history_provider_report=compact_provider_report(history_audit.report()),
        history_provider_calls=history_audit.record_count,
        residual_transform=residual_transform,
    )


def load_reconciled_hydraulic_case() -> DynamicCase:
    """Rebuild the accepted hydraulic total-reboiler test checkpoint."""
    return _load_hydraulic_case(
        report_source=SOURCE_RECONCILED_HYDRAULIC_ROOT,
        matrix_source=SOURCE_RECONCILED_HYDRAULIC_MATRIX,
        expected_reboiler_type="total",
    )


def load_partial_hydraulic_case() -> DynamicCase:
    """Rebuild the accepted hydraulic partial-reboiler case checkpoint."""
    return _load_hydraulic_case(
        report_source=SOURCE_PARTIAL_HYDRAULIC_ROOT,
        matrix_source=SOURCE_PARTIAL_HYDRAULIC_MATRIX,
        expected_reboiler_type="partial",
    )


def solve_nominal_step(
    case: DynamicCase,
    reference: VaporHoldupImplicitReference,
    *,
    timestep_sec: float,
    step_id: str,
    initial_guess: np.ndarray | None = None,
    balance_inputs: Any | None = None,
    expected_feed_multiplier: float = 1.0,
) -> SolvedStep:
    if hasattr(case.provider, "set_exact_state_memoization"):
        case.provider.set_exact_state_memoization(True, clear=True)
    numerical = numerical_spec(
        case.problem,
        timestep_sec=timestep_sec,
        top_pressure_psia=float(case.post_pulse_reference.pressure_psia[0]),
    )
    audit = ProviderCallAudit(**case.problem["provider_audit_kwargs"])
    counters = {"function": 0, "jacobian": 0}
    active_inputs = case.base_inputs if balance_inputs is None else balance_inputs
    feed_multiplier = float(expected_feed_multiplier)
    if not np.isfinite(feed_multiplier) or feed_multiplier <= 0.0:
        raise ValueError("expected feed multiplier must be positive and finite")

    def evaluate_candidate(
        candidate: np.ndarray, *, state_id: str, evaluation_kind: str
    ) -> Any:
        evaluation = evaluate_vapor_holdup_implicit_residual(
            case.contract,
            case.problem["geometry"],
            reference,
            active_inputs,
            case.problem["spec"].hydraulic_geometry,
            numerical,
            case.provider,
            audit,
            candidate,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        if case.residual_transform is not None:
            evaluation = case.residual_transform(evaluation, numerical)
        return evaluation

    def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
        counters["function"] += 1
        return evaluate_candidate(
            candidate,
            state_id=f"{step_id}:{state_id}:{counters['function']}",
            evaluation_kind="jacobian",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        counters["jacobian"] += 1
        matrix, _groups = colored_central_difference_jacobian(
            objective,
            candidate,
            pattern=case.pattern,
            step=DIFFERENCE_STEP,
            state_id=f"{step_id}:solver_jacobian:{counters['jacobian']}",
        )
        return matrix

    point = (
        np.zeros(len(case.contract.rows), dtype=float)
        if initial_guess is None
        else np.asarray(initial_guess, dtype=float).copy()
    )
    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(case.lower, case.upper),
        method="trf",
        x_scale=case.coordinate_scale,
        ftol=1.0e-11,
        xtol=1.0e-11,
        gtol=1.0e-11,
        max_nfev=MAX_NFEV,
        verbose=0,
    )
    evaluation = evaluate_candidate(
        solution.x,
        state_id=f"{step_id}:final",
        evaluation_kind="residual",
    )
    actual_component = np.sum(
        evaluation.endpoint.liquid_component_inventory_lbmol
        + evaluation.endpoint.vapor_component_inventory_lbmol
        - reference.liquid_component_inventory_lbmol
        - reference.vapor_component_inventory_lbmol,
        axis=0,
    )
    expected_component = (
        evaluation.transport.external_component_rate_lbmolph * timestep_sec / 3600.0
    )
    component_error = float(np.max(np.abs(actual_component - expected_component)))
    actual_energy = float(
        np.sum(
            evaluation.properties.total_stored_energy_BTU
            - reference.total_stored_energy_BTU
        )
    )
    expected_energy = float(
        evaluation.transport.external_energy_rate_BTUph * timestep_sec / 3600.0
    )
    energy_error_absolute = abs(actual_energy - expected_energy)
    energy_error_relative = energy_error_absolute / max(
        abs(actual_energy), abs(expected_energy), 1.0
    )
    residual_norm = float(np.max(np.abs(evaluation.scaled)))
    minimum_bound_distance = float(
        np.min(
            np.minimum(solution.x - case.lower, case.upper - solution.x)
        )
    )
    provider_report = compact_provider_report(audit.report())
    provider_pass = bool(
        provider_report["pass"] and not audit.fallback_attempted
    )
    feed_boundary_exact = bool(
        np.array_equal(
            np.asarray(active_inputs.feed_component_lbmolph),
            feed_multiplier * np.asarray(case.base_inputs.feed_component_lbmolph),
        )
        and float(active_inputs.feed_enthalpy_BTUph)
        == feed_multiplier * float(case.base_inputs.feed_enthalpy_BTUph)
    )
    gates = {
        "solver": bool(solution.success),
        "residual": residual_norm < RESIDUAL_LIMIT,
        "bounds": minimum_bound_distance > 1.0e-6,
        "component_identity": component_error < COMPONENT_IDENTITY_LIMIT_LBMOL,
        "energy_identity": bool(
            energy_error_relative < ENERGY_IDENTITY_RELATIVE_LIMIT
            or energy_error_absolute < ENERGY_IDENTITY_ABSOLUTE_LIMIT_BTU
        ),
        "physical": _physical(evaluation),
        "fugacity": float(np.max(np.abs(evaluation.fugacity_residual))) < 1.0e-8,
        "eos": (
            float(np.max(np.abs(evaluation.properties.eos_relative_residual)))
            < 1.0e-10
        ),
        "provider": provider_pass,
        # Retain the historical gate name for saved-report compatibility. It now
        # means that the requested feed boundary was applied exactly.
        "nominal_feed": feed_boundary_exact,
    }
    gates = {name: bool(value) for name, value in gates.items()}
    metrics = {
        "timestep_sec": float(timestep_sec),
        "expected_feed_multiplier": feed_multiplier,
        "solver_success": bool(solution.success),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "observed": counters,
        "scaled_residual_inf_norm": residual_norm,
        "maximum_coordinate_movement": float(np.max(np.abs(solution.x))),
        "minimum_bound_distance": minimum_bound_distance,
        "component_identity_error_lbmol": component_error,
        "actual_energy_change_BTU": actual_energy,
        "expected_energy_change_BTU": expected_energy,
        "energy_identity_absolute_error_BTU": energy_error_absolute,
        "energy_identity_relative_error": energy_error_relative,
        "maximum_fugacity_residual": float(
            np.max(np.abs(evaluation.fugacity_residual))
        ),
        "maximum_eos_relative_residual": float(
            np.max(np.abs(evaluation.properties.eos_relative_residual))
        ),
        "provider_calls": audit.record_count,
        "gates": gates,
        "pass_gate": all(gates.values()),
    }
    return SolvedStep(
        solution=solution,
        evaluation=evaluation,
        numerical=numerical,
        reference=reference,
        metrics=metrics,
        gates=gates,
        provider_report=provider_report,
        provider_calls=audit.record_count,
        objective=objective,
        audit=audit,
    )


def build_trajectory_end_summary(
    case: DynamicCase,
    evidence: Mapping[str, np.ndarray],
    *,
    state_id: str,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Build the standard final display from saved or in-memory trajectory arrays."""
    if hasattr(case.provider, "set_exact_state_memoization"):
        case.provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit(**case.problem["provider_audit_kwargs"])
    final_properties = evaluate_vapor_holdup_trial_properties(
        case.problem["geometry"],
        np.asarray(evidence["liquid_component_inventory_lbmol"][-1], dtype=float),
        np.asarray(evidence["vapor_component_inventory_lbmol"][-1], dtype=float),
        np.asarray(evidence["temperature_F"][-1], dtype=float),
        np.asarray(evidence["pressure_psia"][-1], dtype=float),
        case.provider,
        audit,
        state_id=state_id,
        evaluation_kind="residual",
    )
    workbook_case = starting_state.load_case_from_excel(str(case.problem["workbook"]))
    terminal_geometry = terminal_geometry_from_specs(workbook_case.specs)
    topology = case.contract.topology.column
    node_types = tuple(
        "reflux_drum"
        if volume == topology.top_volume
        else (
            "reboiler_sump"
            if volume == topology.bottom_volume
            else ("feed_tray" if volume == topology.feed_volume else "tray")
        )
        for volume in topology.volume_ids
    )
    summary = build_end_of_run_summary(
        component_names=case.contract.component_names,
        volume_ids=topology.volume_ids,
        node_types=node_types,
        time_sec=evidence["time_sec"],
        liquid_component_inventory_lbmol=evidence[
            "liquid_component_inventory_lbmol"
        ],
        vapor_component_inventory_lbmol=evidence[
            "vapor_component_inventory_lbmol"
        ],
        temperature_F=evidence["temperature_F"],
        pressure_psia=evidence["pressure_psia"],
        hydraulic_liquid_flow_lbmolph=evidence["liquid_flow_lbmolph"],
        hydraulic_volume_ids=topology.hydraulic_volume_ids,
        vapor_flow_lbmolph=evidence["vapor_flow_lbmolph"],
        vapor_links=topology.vapor_links,
        condenser_duty_BTUph=evidence["condenser_duty_BTUph"],
        reboiler_duty_BTUph=float(case.base_inputs.reboiler_duty_BTUph),
        reflux_lbmolph=float(case.problem["spec"].reflux_lbmolph),
        distillate_lbmolph=float(case.base_inputs.distillate_lbmolph),
        bottoms_lbmolph=float(case.base_inputs.bottoms_lbmolph),
        feed_component_lbmolph=case.base_inputs.feed_component_lbmolph,
        final_liquid_density_lbmol_ft3=(
            final_properties.liquid_density_lbmol_ft3
        ),
        final_liquid_enthalpy_BTU_lbmol=(
            final_properties.liquid_enthalpy_BTU_lbmol
        ),
        final_vapor_enthalpy_BTU_lbmol=(
            final_properties.vapor_enthalpy_BTU_lbmol
        ),
        terminal_geometry=terminal_geometry,
        distillate_flow_history_lbmolph=evidence.get(
            "distillate_flow_lbmolph"
        ),
        bottoms_flow_history_lbmolph=evidence.get("bottoms_flow_lbmolph"),
    )
    provider_report = compact_provider_report(audit.report())
    return summary, provider_report, audit.record_count
