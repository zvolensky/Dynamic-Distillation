#!/usr/bin/env python
"""Prepare or execute DD-223's frozen full-C3/C4 stationary-root campaign."""

from __future__ import annotations

import argparse
from dataclasses import asdict
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

import audit_core_v3_provider_governed_numerical as dd092
import audit_core_v3_full_c3c4_live_readiness as dd222
import run_core_v3_seven_volume_steady_root as dd169

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    BubbleSolveSettings,
    coordinate_layout,
    solve_local_bubble,
    structural_pattern,
    tp_flash_diagnostics,
)
from dynamic_distillation.core_v3.provider_governed_steady_root_v1 import (
    SteadyRootSettings,
    execute_start,
    independent_smooth_start,
    pairwise_root_agreement,
    physical_bounds,
    physical_vector_and_scales,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


SCHEMA = "dd223-core-v3-full-c3c4-steady-root-contract-v1"
RESULT_SCHEMA = "dd223-core-v3-full-c3c4-steady-root-result-v1"
SOURCE_CONTRACT = dd222.CONTRACT
SOURCE_RESULT = Path("logs/dd222_core_v3_full_c3c4_live_readiness_20260815.json")
CONTRACT = Path("logs/dd223_core_v3_full_c3c4_steady_root_contract_20260815.json")
RESULT = Path("logs/dd223_core_v3_full_c3c4_steady_root_20260815")
CALL_LIMIT = 1000000
WALL_LIMIT_SEC = 600.0
MINIMUM_START_SEPARATION = 0.1
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_steady_root_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_full_c3c4_live_readiness.py",
    "tools/run_core_v3_full_c3c4_steady_root.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _float_list(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values).reshape((-1,))]


def _source_model(source: Mapping[str, Any]):
    workbook = Path(source["workbook"])
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    provider = dd092._provider(column, str(source["property_package"]))
    spec = dd222._spec(
        source["source_mapping"],
        float(source["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd222._reference(source["reference"])
    return workbook, provider, spec, reference


def prepare(contract_path: Path) -> dict[str, Any]:
    source, source_commit = dd222._load_committed_contract(ROOT / SOURCE_CONTRACT)
    result = json.loads((ROOT / SOURCE_RESULT).read_text(encoding="utf-8"))
    if not result.get("pass_gate"):
        raise RuntimeError("DD-223 requires the passing DD-222 result")
    workbook, provider, spec, reference = _source_model(source)
    settings = SteadyRootSettings(jacobian_mode="colored")
    lower, upper = physical_bounds(spec, reference, settings)
    preparation_audit = ProviderCallAudit()
    independent, metadata = independent_smooth_start(
        spec,
        reference,
        provider,
        preparation_audit,
        bubble_settings=BubbleSolveSettings(),
    )
    canonical = np.asarray(source["state"], dtype=float)
    starts = {
        "source_mapped_seed": canonical,
        "independent_smooth_topology_seed": independent,
    }
    dimension = canonical.size
    for name, point in starts.items():
        if point.shape != (dimension,):
            raise RuntimeError(f"DD-223 start {name!r} has the wrong dimension")
        if np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-223 start {name!r} is outside frozen bounds")
    separation = float(np.max(np.abs(canonical - independent)))
    if separation <= MINIMUM_START_SEPARATION:
        raise RuntimeError("DD-223 starts are not materially independent")
    groups = greedy_column_groups(structural_pattern(spec))
    if len(groups) != source["jacobian"]["color_count"]:
        raise RuntimeError("DD-223 source coloring changed")
    physical_scales = physical_vector_and_scales(spec, reference, canonical)[1]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "source_contract": str(SOURCE_CONTRACT).replace("\\", "/"),
        "source_contract_commit": source_commit,
        "source_contract_sha256": _sha(ROOT / SOURCE_CONTRACT),
        "source_result": str(SOURCE_RESULT).replace("\\", "/"),
        "source_result_sha256": _sha(ROOT / SOURCE_RESULT),
        "workbook": str(workbook.resolve()),
        "workbook_sha256": _sha(workbook),
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "fixed_residual_scales": source["fixed_residual_scales"],
        "settings": asdict(settings),
        "lower_bounds": _float_list(lower),
        "upper_bounds": _float_list(upper),
        "physical_comparison_scales": _float_list(physical_scales),
        "starts": {name: _float_list(point) for name, point in starts.items()},
        "start_separation_inf": separation,
        "independent_start_metadata": metadata,
        "jacobian": {
            "mode": "colored",
            "color_count": len(groups),
            "color_groups": [list(group) for group in groups],
            "central_difference_residual_evaluations_per_matrix": 2 * len(groups),
            "uncolored_equivalent_per_matrix": 2 * dimension,
        },
        "exact_state_memoization": {
            "enabled_per_start": True,
            "exact_unrounded_keys": True,
            "cleared_before_each_start": True,
            "acceptance_decisions_use_unchanged_residuals": True,
        },
        "limits": {
            "logical_provider_calls": CALL_LIMIT,
            "wall_clock_sec": WALL_LIMIT_SEC,
            "minimum_start_separation": MINIMUM_START_SEPARATION,
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "preparation_provider_provenance": preparation_audit.report(),
        "full_residual_evaluated_during_preparation": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "hard_stops": [
            "either start fails or reaches max_nfev",
            "scaled residual remains at or above 1e-8",
            "roots disagree physically at or above 1e-7",
            "an endpoint is rank deficient, ill-conditioned, or finite-difference unstable",
            "a bound becomes active",
            "physicality, ordering, phase, conservation, or provider ownership fails",
            "call or wall limit is exceeded",
            "a retry, fallback, continuation, clipping, projection, or post-result change occurs",
        ],
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-223 contract already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-223 Frozen Full-C3/C4 Stationary-Root Contract",
                "",
                f"- Dimension: `{dimension}`",
                f"- Starts: `{', '.join(starts)}`",
                f"- Start separation: `{separation:.6e}`",
                f"- Jacobian colors: `{len(groups)}`",
                f"- Colored/uncolored evaluations per matrix: `{2 * len(groups)} / {2 * dimension}`",
                "- Solver: `least_squares(method=trf)`",
                "- Nonlinear solve during preparation: `False`",
                "- Timestep or integration: `False`",
                "",
                "One execution is authorized after commit. No retry is permitted.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _load_committed(path: Path) -> tuple[dict[str, Any], str]:
    destination = ROOT / path
    relative = destination.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    if committed.replace("\r\n", "\n").strip() != destination.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n").strip():
        raise RuntimeError("DD-223 contract differs from committed content")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-223 contract schema or checksum failed")
    for implementation, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / implementation) != digest:
            raise RuntimeError(f"DD-223 implementation changed: {implementation}")
    for key in ("source_contract", "source_result"):
        if _sha(ROOT / payload[key]) != payload[f"{key}_sha256"]:
            raise RuntimeError(f"DD-223 {key} changed")
    return payload, _git("rev-parse", "HEAD")


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed(contract_path)
    source = json.loads((ROOT / contract["source_contract"]).read_text(encoding="utf-8"))
    _workbook, provider, spec, reference = _source_model(source)
    settings = SteadyRootSettings(**contract["settings"])
    lower = np.asarray(contract["lower_bounds"], dtype=float)
    upper = np.asarray(contract["upper_bounds"], dtype=float)
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    started = time.perf_counter()
    results: dict[str, dict[str, Any]] = {}
    memo: dict[str, Any] = {}
    for name, values in contract["starts"].items():
        provider.set_exact_state_memoization(True, clear=True)
        start = execute_start(
            spec,
            reference,
            provider,
            name=name,
            initial=values,
            lower_bounds=lower,
            upper_bounds=upper,
            fixed_scales=scales,
            settings=settings,
        )
        memo[name] = provider.get_exact_state_memoization_stats()
        provider.set_exact_state_memoization(False, clear=True)
        results[name] = start
    agreement = pairwise_root_agreement(
        spec,
        reference,
        {name: start["final_coordinates"] for name, start in results.items()},
        contract["physical_comparison_scales"],
    )
    independent = dd092._independent_provider(source)
    diagnostic_audit = ProviderCallAudit()
    diagnostics: dict[str, Any] = {}
    start_passes: dict[str, bool] = {}
    for name, start in results.items():
        evaluation = start["endpoint_evaluation"]
        state = evaluation.state
        flash = tp_flash_diagnostics(
            provider,
            diagnostic_audit,
            temperature_F=float(state.temperature_F[0]),
            pressure_psia=float(spec.pressure_psia[0]),
            overall_z=state.liquid_mole_fraction[0],
            state_id=name,
        )
        bubble = solve_local_bubble(
            independent,
            diagnostic_audit,
            pressure_psia=float(spec.pressure_psia[0]),
            liquid_x=state.liquid_mole_fraction[0],
            temperature_guess_F=float(state.temperature_F[0]),
            vapor_guess=state.bubble_vapor_mole_fraction,
            state_id=name,
            evaluation_kind="validation",
            independent=True,
            settings=BubbleSolveSettings(),
        )
        jacobians = start["endpoint_jacobians"]
        spectrum_change = float(
            np.max(
                np.abs(jacobians[0].singular_values - jacobians[1].singular_values)
                / np.maximum(np.abs(jacobians[0].singular_values), 1.0e-15)
            )
        )
        independent_temperature = float(bubble.temperature_F - state.temperature_F[0])
        independent_composition = float(
            np.max(np.abs(bubble.vapor_mole_fraction - state.bubble_vapor_mole_fraction))
        )
        flash_pass = bool(
            not flash["stable_vapor"]
            and flash["vapor_fraction"] <= settings.tp_flash_vapor_fraction_tolerance
            and flash["flash_Kx_identity_max_abs"] < settings.tp_flash_internal_tolerance
            and flash["lever_rule_closure_max_abs"] < settings.tp_flash_internal_tolerance
        )
        independent_pass = bool(
            bubble.success
            and abs(independent_temperature) < settings.independent_pr_temperature_tolerance_F
            and independent_composition < settings.independent_pr_composition_tolerance
        )
        jacobian_pass = all(
            item.rank == len(contract["lower_bounds"])
            and item.condition < settings.jacobian_condition_hard_stop
            and item.bubble_rank == len(spec.component_names)
            and not item.zero_rows and not item.zero_columns and not item.unexpected_couplings
            for item in jacobians
        )
        physical_pass = bool(
            np.all(state.liquid_moles_lbmol > 0.0)
            and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(state.vapor_flow_lbmolph > 0.0)
            and state.distillate_lbmolph > 0.0
            and state.bottoms_lbmolph > 0.0
            and state.condenser_duty_BTUph < 0.0
            and np.all(np.diff(state.temperature_F) > 0.0)
            and np.all(np.diff(spec.pressure_psia) >= 0.0)
            and np.all(start["liquid_heights_ft"] < start["tray_spacings_ft"])
            and np.all(state.liquid_mole_fraction > 0.0)
            and np.all(state.vapor_mole_fraction > 0.0)
        )
        passed = bool(
            start["success_flag"]
            and start["nfev"] <= settings.max_nfev
            and np.max(np.abs(evaluation.scaled)) < settings.residual_inf_tolerance
            and start["final_block_norms"]["full_phase_equilibrium"] < settings.fugacity_residual_tolerance
            and start["final_block_norms"]["condenser_bubble_fugacity"] < settings.bubble_residual_tolerance
            and not len(start["active_bound_indices"])
            and jacobian_pass
            and spectrum_change < settings.singular_value_relative_stability_tolerance
            and evaluation.component_telescoping_relative_error < settings.component_conservation_tolerance
            and evaluation.energy_telescoping_relative_error < settings.energy_conservation_tolerance
            and physical_pass and flash_pass and independent_pass
            and start["provider_provenance"]["pass"]
            and not evaluation.clipping_or_projection_used
            and not evaluation.property_fallback_used
        )
        start_passes[name] = passed
        diagnostics[name] = {
            "spectrum_relative_change": spectrum_change,
            "physical_pass": physical_pass,
            "jacobian_pass": jacobian_pass,
            "tp_flash": dd092._json_diagnostic(flash),
            "tp_flash_pass": flash_pass,
            "independent_pr_temperature_difference_F": independent_temperature,
            "independent_pr_vapor_max_abs": independent_composition,
            "independent_pr_pass": independent_pass,
            "pass": passed,
        }
    elapsed = time.perf_counter() - started
    logical_calls = sum(
        int(start["provider_provenance"]["total_calls"])
        for start in results.values()
    ) + int(diagnostic_audit.report()["total_calls"])
    common_root_pass = bool(max(agreement.values()) < settings.common_root_tolerance)
    campaign_pass = bool(
        all(start_passes.values())
        and common_root_pass
        and diagnostic_audit.report()["pass"]
        and logical_calls < contract["limits"]["logical_provider_calls"]
        and elapsed < contract["limits"]["wall_clock_sec"]
    )
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "full_c3c4_stationary_root_passed"
            if campaign_pass else "full_c3c4_stationary_root_failed"
        ),
        "decision": (
            "authorize_structural_full_c3c4_dynamic_dae_contract"
            if campaign_pass else "stop_full_c3c4_root_path_without_retry"
        ),
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "starts": {name: dd169._json_start(start) for name, start in results.items()},
        "endpoint_diagnostics": diagnostics,
        "start_passes": start_passes,
        "pairwise_physical_root_agreement": agreement,
        "common_root_pass": common_root_pass,
        "jacobian_color_count": contract["jacobian"]["color_count"],
        "exact_state_memoization": memo,
        "diagnostic_provider_provenance": diagnostic_audit.report(),
        "logical_provider_calls": logical_calls,
        "wall_clock_sec": elapsed,
        "campaign_pass": campaign_pass,
        "campaign_executed_once": True,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-223 Full-C3/C4 Stationary-Root Campaign",
                "",
                f"- Classification: `{report['classification']}`",
                f"- Decision: `{report['decision']}`",
                f"- Common-root maximum: `{max(agreement.values()):.6e}`",
                f"- Logical provider calls: `{logical_calls}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "- Timestep or integration: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--out-prefix", type=Path, default=RESULT)
    args = parser.parse_args()
    output = prepare(args.contract) if args.prepare_only else execute(args.contract, args.out_prefix)
    print(json.dumps(output, indent=2))
    return 0 if args.prepare_only or output["campaign_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
