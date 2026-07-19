#!/usr/bin/env python
"""Prepare or execute the frozen DD-093 Core V3 steady-root campaign."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    BubbleSolveSettings,
    HydraulicGeometry,
    IndependentPengRobinsonProvider,
    NumericalReference,
    OperatingSpec,
    PengRobinsonParameters,
    decode_coordinates,
    solve_local_bubble,
    tp_flash_diagnostics,
)
from dynamic_distillation.core_v3.provider_governed_steady_root_v1 import (
    SteadyRootSettings,
    execute_start,
    pairwise_root_agreement,
    prepare_campaign,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA_ID = "dd093-core-v3-steady-root-contract-v1"
RESULT_SCHEMA_ID = "dd093-core-v3-steady-root-result-v1"
DD092_CONTRACT = Path(
    "logs/dd092_core_v3_provider_governed_numerical_contract_20260719.json"
)
IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/__init__.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_steady_root_v1.py",
    "tests/test_core_v3_provider_governed_registry_v1.py",
    "tests/test_core_v3_provider_call_audit_v1.py",
    "tests/test_core_v3_provider_governed_residual_v1.py",
    "tests/test_core_v3_provider_governed_steady_root_v1.py",
    "tools/run_core_v3_provider_governed_steady_root.py",
    "docs/dd_093_core_v3_steady_root_contract_20260719.md",
)


def _vector(values: Any) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _load_hashed_json(path: Path, hash_key: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = str(payload.pop(hash_key))
    actual = _payload_hash(payload)
    if claimed != actual:
        raise RuntimeError(f"{path} payload hash mismatch")
    payload[hash_key] = claimed
    return payload


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
            HydraulicGeometry(**item)
            for item in source["hydraulic_geometry"]
        ),
    )


def _reference(payload: Mapping[str, Any]) -> NumericalReference:
    return NumericalReference(
        liquid_moles_lbmol=np.asarray(
            payload["liquid_moles_lbmol"], dtype=float
        ),
        liquid_mole_fraction=np.asarray(
            payload["liquid_mole_fraction"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(
            payload["vapor_mole_fraction"], dtype=float
        ),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(
            payload["vapor_flow_lbmolph"], dtype=float
        ),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_reference_BTUph=float(
            payload["condenser_duty_reference_BTUph"]
        ),
        condenser_duty_scale_BTUph=float(
            payload["condenser_duty_scale_BTUph"]
        ),
    )


def _provider(workbook: Path, package: str) -> ThermoProviderV1:
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    return ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=package,
        silence_backend_console=True,
    )


def _independent_provider(
    dd092: Mapping[str, Any],
) -> IndependentPengRobinsonProvider:
    raw = dd092["independent_pr_parameters"]
    return IndependentPengRobinsonProvider(
        PengRobinsonParameters(
            critical_temperature_K=np.asarray(
                raw["critical_temperature_K"], dtype=float
            ),
            critical_pressure_Pa=np.asarray(
                raw["critical_pressure_Pa"], dtype=float
            ),
            acentric_factor=np.asarray(
                raw["acentric_factor"], dtype=float
            ),
            binary_interaction=np.asarray(
                raw["binary_interaction"], dtype=float
            ),
        )
    )


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-093 Frozen Core V3 Steady-Root Contract",
            "",
            f"- Schema: `{payload['schema_id']}`",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            f"- DD-092 payload: `{payload['dd092_contract_payload_sha256']}`",
            "- System: unchanged Core V3 `40 x 40` residual",
            "- Solver: `scipy.optimize.least_squares(method=\"trf\")`",
            "- Starts: three complete 40-coordinate vectors",
            "- Campaign executed during preparation: `False`",
            "",
            "## Third Start",
            "",
            "The third start is a fully distinct smooth five-volume profile, "
            "including a separately selected drum liquid composition, its own "
            "direct-fugacity bubble reconstruction, and its own condenser-energy "
            "duty reconstruction.",
            "",
            "## Authorization",
            "",
            "This commit defines the one permitted campaign. It does not execute "
            "the nonlinear solve or authorize dynamic work.",
            "",
        )
    )


def prepare(dd092_path: Path, contract_path: Path) -> dict[str, Any]:
    dd092 = _load_hashed_json(dd092_path, "contract_payload_sha256")
    workbook = Path(dd092["workbook"])
    if _sha256(workbook) != dd092["workbook_sha256"]:
        raise RuntimeError("DD-092 workbook has changed")
    spec = _spec(
        dd092["source_mapping"],
        float(dd092["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = _reference(dd092["reference"])
    provider = _provider(workbook, str(dd092["property_package"]))
    audit = ProviderCallAudit()
    settings = SteadyRootSettings()
    campaign, independent = prepare_campaign(
        spec,
        reference,
        provider,
        audit,
        settings,
        canonical=dd092["states"]["canonical_core_v3_state"],
        perturbation=dd092["states"][
            "deterministic_combined_perturbation"
        ],
        fixed_residual_scales=dd092["fixed_residual_scales"],
    )
    hashes = {
        path: _sha256(ROOT / path)
        for path in IMPLEMENTATION_PATHS
        if (ROOT / path).exists()
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd092_contract_path": str(dd092_path.resolve()),
        "dd092_contract_payload_sha256": dd092[
            "contract_payload_sha256"
        ],
        "dd092_contract_commit": "1ffa504beda0df0c805260401c9d7a5f70cf98cb",
        "workbook": str(workbook.resolve()),
        "workbook_sha256": dd092["workbook_sha256"],
        "property_package": dd092["property_package"],
        "source_mapping": dd092["source_mapping"],
        "operating_spec": dd092["operating_spec"],
        "reference": dd092["reference"],
        "independent_pr_parameters": dd092["independent_pr_parameters"],
        "coordinate_names": dd092["coordinate_names"],
        "residual_names": dd092["residual_names"],
        "fixed_residual_scales": _vector(
            campaign.fixed_residual_scales
        ),
        "physical_comparison_scales": _vector(
            campaign.physical_comparison_scales
        ),
        "lower_bounds": _vector(campaign.lower_bounds),
        "upper_bounds": _vector(campaign.upper_bounds),
        "starts": {
            name: _vector(point)
            for name, point in campaign.starts.items()
        },
        "start_construction": {
            "canonical": "exact DD-092 canonical vector",
            "perturbation": "exact DD-092 deterministic perturbation",
            "independent": independent,
        },
        "solver_settings": asdict(settings),
        "physical_bounds": {
            "temperature_F": [110.0, 260.0],
            "terminal_liquid_amount_ratio": [0.8, 1.2],
            "interior_liquid_amount_ratio": [0.2, 2.0],
            "composition_floor": 1.0e-10,
            "internal_flow_reference_ratio": [0.1, 5.0],
            "product_feed_ratio": [1.0e-4, 1.05],
            "condenser_duty_reference_abs_ratio": [-3.0, -0.1],
        },
        "provider_authority": {
            "governing": [
                "dwsim.direct_imposed_phase_fugacity",
                "dwsim.declared_phase_enthalpy",
                "dwsim.declared_liquid_density",
            ],
            "diagnostic_only_after_residual_and_jacobian": [
                "dwsim.tp_flash"
            ],
            "validation_only": [
                "independent.parameter_aligned_peng_robinson"
            ],
            "mixed_basis_K_flash_z_gate_permitted": False,
            "direct_y_equals_flash_y_gate_permitted": False,
            "interface_fallback_permitted": False,
        },
        "required_report_fields": [
            "termination_reason",
            "nfev_njev_wall_clock_property_calls",
            "initial_final_residual_block_norms",
            "movement_by_coordinate_family",
            "endpoint_rank_condition_singular_values",
            "minimum_bound_distance",
            "final_state_flows_duty",
            "tray_heights_residence_times",
            "direct_bubble_residual",
            "independent_pr_differences",
            "tp_phase_beta_identity_lever_rule",
            "provider_provenance",
            "component_energy_external_closure",
        ],
        "hard_stops": [
            "any_start_residual_above_1e-8",
            "pairwise_physical_root_difference_above_1e-7",
            "bound_distance_at_or_below_1e-6",
            "rank_below_40_or_local_bubble_rank_below_3",
            "condition_above_1e8",
            "provider_ownership_violation",
            "nonnegative_condenser_duty",
            "stable_vapor_or_beta_above_1e-3",
            "direct_bubble_or_independent_pr_failure",
            "tp_flash_internal_algebra_failure",
            "conservation_or_physical_geometry_failure",
            "safeguard_fallback_controller_limiter_or_profile_forcing",
        ],
        "prohibited_followups_after_failure": [
            "solver_or_tolerance_tuning",
            "wider_bounds",
            "duty_or_pressure_sweep",
            "provider_substitution",
            "dd088_root_import",
            "dynamic_work",
        ],
        "implementation_sha256": hashes,
        "preparation_provider_provenance": audit.report(),
        "full_residual_evaluated_during_preparation": False,
        "campaign_executed": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    contract_path.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify_committed(contract_path: Path) -> str:
    relative = contract_path.resolve().relative_to(ROOT).as_posix()
    commit = _git("log", "-1", "--format=%H", "--", relative)
    if not commit:
        raise RuntimeError("DD-093 contract is not committed")
    tracked = [relative, *IMPLEMENTATION_PATHS]
    if _git("status", "--short", "--", *tracked):
        raise RuntimeError("DD-093 contract implementation is not clean")
    return commit


def _verify_hashes(contract: Mapping[str, Any]) -> None:
    for relative, expected in contract["implementation_sha256"].items():
        if _sha256(ROOT / relative) != expected:
            raise RuntimeError(f"DD-093 implementation changed: {relative}")


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return _jsonable(value.__dict__)
    return value


def execute(contract_path: Path, out_path: Path) -> dict[str, Any]:
    """Execute only after the separately committed DD-093 contract."""
    contract_commit = _verify_committed(contract_path)
    contract = _load_hashed_json(contract_path, "contract_payload_sha256")
    _verify_hashes(contract)
    workbook = Path(contract["workbook"])
    spec = _spec(
        contract["source_mapping"],
        float(contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = _reference(contract["reference"])
    provider = _provider(workbook, str(contract["property_package"]))
    independent = _independent_provider(contract)
    settings = SteadyRootSettings(**contract["solver_settings"])
    results: dict[str, Any] = {}
    endpoints: dict[str, np.ndarray] = {}
    for name, initial in contract["starts"].items():
        result = execute_start(
            spec,
            reference,
            provider,
            name=name,
            initial=initial,
            lower_bounds=contract["lower_bounds"],
            upper_bounds=contract["upper_bounds"],
            fixed_scales=contract["fixed_residual_scales"],
            settings=settings,
        )
        endpoint = result["endpoint_evaluation"]
        state = endpoint.state
        diagnostics = ProviderCallAudit()
        flash = tp_flash_diagnostics(
            provider,
            diagnostics,
            temperature_F=float(state.temperature_F[0]),
            pressure_psia=float(spec.pressure_psia[0]),
            overall_z=state.liquid_mole_fraction[0],
            state_id=name,
        )
        independent_bubble = solve_local_bubble(
            independent,
            diagnostics,
            pressure_psia=float(spec.pressure_psia[0]),
            liquid_x=state.liquid_mole_fraction[0],
            temperature_guess_F=float(state.temperature_F[0]),
            vapor_guess=state.bubble_vapor_mole_fraction,
            state_id=name,
            evaluation_kind="validation",
            independent=True,
            settings=BubbleSolveSettings(),
        )
        raw_fugacity = [
            abs(float(endpoint.raw[index]))
            for index, row in enumerate(endpoint.rows)
            if row.block in {
                "full_phase_equilibrium",
                "condenser_bubble_fugacity",
            }
        ]
        endpoint_jacobians = result["endpoint_jacobians"]
        singular_left = endpoint_jacobians[0].singular_values
        singular_right = endpoint_jacobians[1].singular_values
        singular_stability = float(
            np.max(
                np.abs(singular_left - singular_right)
                / np.maximum(
                    np.maximum(np.abs(singular_left), np.abs(singular_right)),
                    np.finfo(float).tiny,
                )
            )
        )
        bubble_left = endpoint_jacobians[0].bubble_singular_values
        bubble_right = endpoint_jacobians[1].bubble_singular_values
        bubble_singular_stability = float(
            np.max(
                np.abs(bubble_left - bubble_right)
                / np.maximum(
                    np.maximum(np.abs(bubble_left), np.abs(bubble_right)),
                    np.finfo(float).tiny,
                )
            )
        )
        jacobian_pass = bool(
            all(
                item.rank == 40
                and item.bubble_rank == 3
                and item.condition
                < settings.jacobian_condition_hard_stop
                and not item.zero_rows
                and not item.zero_columns
                and not item.unexpected_couplings
                and not item.bubble_zero_rows
                and not item.bubble_zero_columns
                for item in endpoint_jacobians
            )
            and singular_stability
            < settings.singular_value_relative_stability_tolerance
            and bubble_singular_stability
            < settings.singular_value_relative_stability_tolerance
        )
        independent_delta_T = float(
            independent_bubble.temperature_F - state.temperature_F[0]
        )
        independent_delta_y = float(
            np.max(
                np.abs(
                    independent_bubble.vapor_mole_fraction
                    - state.bubble_vapor_mole_fraction
                )
            )
        )
        compositions = np.concatenate(
            (
                state.liquid_mole_fraction.reshape((-1,)),
                state.vapor_mole_fraction.reshape((-1,)),
                state.bubble_vapor_mole_fraction,
            )
        )
        physical_pass = bool(
            np.all(np.isfinite(endpoint.raw))
            and np.all(state.liquid_moles_lbmol > 0.0)
            and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(state.vapor_flow_lbmolph > 0.0)
            and state.distillate_lbmolph > 0.0
            and state.bottoms_lbmolph > 0.0
            and state.condenser_duty_BTUph < 0.0
            and state.temperature_F[0] < state.temperature_F[1]
            and np.all(compositions >= settings.composition_floor)
            and np.all(
                np.asarray(result["liquid_heights_ft"])
                < np.asarray(result["tray_spacings_ft"])
            )
            and not endpoint.clipping_or_projection_used
            and not endpoint.property_fallback_used
        )
        tp_pass = bool(
            not flash["stable_vapor"]
            and flash["vapor_fraction"]
            <= settings.tp_flash_vapor_fraction_tolerance
            and flash["flash_Kx_identity_max_abs"]
            < settings.tp_flash_internal_tolerance
            and flash["lever_rule_closure_max_abs"]
            < settings.tp_flash_internal_tolerance
        )
        independent_pass = bool(
            independent_bubble.success
            and abs(independent_delta_T)
            < settings.independent_pr_temperature_tolerance_F
            and independent_delta_y
            < settings.independent_pr_composition_tolerance
        )
        residual_pass = bool(
            np.max(np.abs(endpoint.scaled))
            < settings.residual_inf_tolerance
            and max(raw_fugacity)
            < settings.fugacity_residual_tolerance
        )
        conservation_pass = bool(
            endpoint.component_telescoping_relative_error
            < settings.component_conservation_tolerance
            and endpoint.energy_telescoping_relative_error
            < settings.energy_conservation_tolerance
        )
        provenance_pass = bool(
            result["provider_provenance"]["pass"]
            and diagnostics.report()["pass"]
        )
        start_pass = bool(
            result["success_flag"]
            and residual_pass
            and jacobian_pass
            and conservation_pass
            and physical_pass
            and tp_pass
            and independent_pass
            and provenance_pass
            and result["minimum_transformed_bound_distance"]
            > settings.active_bound_tolerance
        )
        endpoints[name] = np.asarray(result["final_coordinates"])
        results[name] = {
            **{key: value for key, value in result.items()
               if key not in {"endpoint_evaluation", "endpoint_jacobians"}},
            "endpoint_evaluation": endpoint,
            "endpoint_jacobians": result["endpoint_jacobians"],
            "tp_flash_diagnostic": flash,
            "independent_pr_bubble": independent_bubble,
            "independent_pr_temperature_difference_F": independent_delta_T,
            "independent_pr_vapor_max_abs": independent_delta_y,
            "diagnostic_provider_provenance": diagnostics.report(),
            "residual_pass": residual_pass,
            "jacobian_pass": jacobian_pass,
            "singular_value_relative_change": singular_stability,
            "bubble_singular_value_relative_change": (
                bubble_singular_stability
            ),
            "conservation_pass": conservation_pass,
            "physical_pass": physical_pass,
            "tp_flash_pass": tp_pass,
            "independent_pr_pass": independent_pass,
            "provider_provenance_pass": provenance_pass,
            "start_pass": start_pass,
        }
    agreement = pairwise_root_agreement(
        spec,
        reference,
        endpoints,
        contract["physical_comparison_scales"],
    )
    common_root_pass = bool(
        max(agreement.values()) < settings.common_root_tolerance
    )
    campaign_pass = bool(
        common_root_pass
        and all(result["start_pass"] for result in results.values())
    )
    report = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": contract_commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "starts": _jsonable(results),
        "pairwise_physical_root_agreement": agreement,
        "common_root_pass": common_root_pass,
        "campaign_pass": campaign_pass,
        "classification": (
            "dd093_core_v3_steady_root_passed"
            if campaign_pass
            else "dd093_core_v3_steady_root_failed"
        ),
        "decision": (
            "authorize_structural_dynamic_dae_contract_only"
            if campaign_pass
            else "retire_core_v3_steady_root_campaign_without_tuning"
        ),
        "campaign_executed_once": True,
        "dynamic_integration_attempted": False,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd092-contract", type=Path, default=DD092_CONTRACT)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "logs/dd093_core_v3_steady_root_contract_20260719.json"
        ),
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("logs/dd093_core_v3_steady_root_20260719.json"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare_only:
        output = prepare(args.dd092_contract, args.contract)
        summary = {
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output[
                "contract_payload_sha256"
            ],
            "start_lengths": {
                name: len(point)
                for name, point in output["starts"].items()
            },
            "campaign_executed": False,
        }
    else:
        output = execute(args.contract, args.result)
        summary = {
            "schema_id": output["schema_id"],
            "contract_commit": output["contract_commit"],
            "campaign_executed_once": True,
        }
    print(json.dumps(summary, indent=2))
