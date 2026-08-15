#!/usr/bin/env python
"""Prepare or execute DD-231's frozen full-C3/C4 aligned-density root campaign."""

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
import audit_core_v3_aligned_pr_density_parity as dd229
import run_core_v3_full_c3c4_steady_root as dd223
import run_core_v3_seven_volume_steady_root as dd169

from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    BubbleSolveSettings,
    solve_local_bubble,
    tp_flash_diagnostics,
)
from dynamic_distillation.core_v3.provider_governed_steady_root_v1 import (
    SteadyRootSettings,
    execute_start,
    pairwise_root_agreement,
)


SCHEMA = "dd231-core-v3-full-c3c4-aligned-density-root-contract-v1"
RESULT_SCHEMA = "dd231-core-v3-full-c3c4-aligned-density-root-result-v1"
SOURCE_SCALING = Path("logs/dd230_core_v3_full_c3c4_coordinate_scaling_20260815.json")
SOURCE_PARITY = Path("logs/dd229_core_v3_aligned_pr_density_parity_20260815.json")
SOURCE_REPLAY = Path("logs/dd225_core_v3_dd223_endpoint_replay_20260815.json")
SOURCE_ROOT_CONTRACT = dd223.CONTRACT
CONTRACT = Path("logs/dd231_core_v3_full_c3c4_aligned_density_root_contract_20260815.json")
RESULT = Path("logs/dd231_core_v3_full_c3c4_aligned_density_root_20260815")
CALL_LIMIT = 1000000
WALL_LIMIT_SEC = 600.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_steady_root_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_full_c3c4_live_readiness.py",
    "tools/run_core_v3_full_c3c4_steady_root.py",
    "tools/audit_core_v3_aligned_pr_density_parity.py",
    "tools/run_core_v3_full_c3c4_aligned_density_root.py",
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


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def prepare(contract_path: Path) -> dict[str, Any]:
    scaling = _load(SOURCE_SCALING)
    parity = _load(SOURCE_PARITY)
    replay = _load(SOURCE_REPLAY)
    root_contract = _load(SOURCE_ROOT_CONTRACT)
    if not scaling.get("pass_gate") or not parity.get("pass_gate") or not replay.get("pass_gate"):
        raise RuntimeError("DD-231 requires passing DD-225/DD-229/DD-230 evidence")
    settings = SteadyRootSettings(jacobian_mode="colored")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (SOURCE_SCALING, SOURCE_PARITY, SOURCE_REPLAY, SOURCE_ROOT_CONTRACT)
        },
        "source_model_contract": root_contract["source_contract"],
        "source_model_contract_sha256": _sha(ROOT / root_contract["source_contract"]),
        "workbook": root_contract["workbook"],
        "workbook_sha256": root_contract["workbook_sha256"],
        "provider_routing": parity["provider_routing"],
        "settings": asdict(settings),
        "lower_bounds": root_contract["lower_bounds"],
        "upper_bounds": root_contract["upper_bounds"],
        "fixed_residual_scales": root_contract["fixed_residual_scales"],
        "physical_comparison_scales": root_contract["physical_comparison_scales"],
        "coordinate_scale": scaling["coordinate_scale"],
        "starts": {
            name: endpoint["coordinates"] for name, endpoint in replay["endpoints"].items()
        },
        "limits": {
            "logical_provider_calls": CALL_LIMIT,
            "wall_clock_sec": WALL_LIMIT_SEC,
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "provider_calls_during_preparation": 0,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "hard_stops": [
            "either start fails, reaches max_nfev, or remains above 1e-8",
            "the roots disagree physically at or above 1e-7",
            "an endpoint loses rank, exceeds 1e8 condition, or has unstable spectra",
            "a bound, physicality, conservation, phase, or provider gate fails",
            "a call or wall limit is exceeded",
            "any retry, tuning, continuation, fallback, timestep, or integration occurs",
        ],
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-231 contract already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-231 Frozen Full-C3/C4 Aligned-Density Root Contract",
                "",
                f"- Starts: `{', '.join(payload['starts'])}`",
                "- Solver: `least_squares(method=trf)` with 15-color Jacobian",
                "- Coordinate scale: exact DD-230 vector",
                "- Density: aligned PR smallest positive root",
                "- Fugacity and enthalpy: DWSIM",
                "- Timestep or dynamics: `False`",
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
    if committed.replace("\r\n", "\n").strip() != destination.read_text(encoding="utf-8").replace("\r\n", "\n").strip():
        raise RuntimeError("DD-231 contract differs from committed content")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-231 contract schema or checksum failed")
    for path, digest in payload["sources"].items():
        if _sha(ROOT / path) != digest:
            raise RuntimeError(f"DD-231 source changed: {path}")
    for path, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != digest:
            raise RuntimeError(f"DD-231 implementation changed: {path}")
    if _sha(ROOT / payload["source_model_contract"]) != payload["source_model_contract_sha256"]:
        raise RuntimeError("DD-231 model contract changed")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-231 workbook changed")
    return payload, _git("rev-parse", "HEAD")


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed(contract_path)
    model_contract = _load(Path(contract["source_model_contract"]))
    _workbook, dwsim, spec, reference = dd223._source_model(model_contract)
    aligned = dd092._independent_provider(model_contract)
    provider = dd229.DensityRoutedProvider(dwsim, aligned)
    settings = SteadyRootSettings(**contract["settings"])
    lower = np.asarray(contract["lower_bounds"], dtype=float)
    upper = np.asarray(contract["upper_bounds"], dtype=float)
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    coordinate_scale = np.asarray(contract["coordinate_scale"], dtype=float)
    started = time.perf_counter()
    starts: dict[str, Any] = {}
    for name, values in contract["starts"].items():
        provider.set_exact_state_memoization(True, clear=True)
        audit = ProviderCallAudit(
            provider_identity="dwsim",
            interface_provider_identities={"declared_liquid_density": "aligned_pr"},
        )
        starts[name] = execute_start(
            spec,
            reference,
            provider,
            name=name,
            initial=values,
            lower_bounds=lower,
            upper_bounds=upper,
            fixed_scales=scales,
            settings=settings,
            call_audit=audit,
            coordinate_scale=coordinate_scale,
        )
        provider.set_exact_state_memoization(False, clear=True)
    agreement = pairwise_root_agreement(
        spec,
        reference,
        {name: item["final_coordinates"] for name, item in starts.items()},
        contract["physical_comparison_scales"],
    )
    diagnostic_audit = ProviderCallAudit()
    independent = dd092._independent_provider(model_contract)
    diagnostics: dict[str, Any] = {}
    start_passes: dict[str, bool] = {}
    for name, item in starts.items():
        evaluation = item["endpoint_evaluation"]
        state = evaluation.state
        flash = tp_flash_diagnostics(
            dwsim,
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
        jacobians = item["endpoint_jacobians"]
        spectrum_change = float(
            np.max(
                np.abs(jacobians[0].singular_values - jacobians[1].singular_values)
                / np.maximum(np.abs(jacobians[0].singular_values), 1.0e-15)
            )
        )
        phase_pass = bool(
            not flash["stable_vapor"]
            and flash["vapor_fraction"] <= settings.tp_flash_vapor_fraction_tolerance
            and bubble.success
            and abs(bubble.temperature_F - state.temperature_F[0])
            < settings.independent_pr_temperature_tolerance_F
            and np.max(np.abs(bubble.vapor_mole_fraction - state.bubble_vapor_mole_fraction))
            < settings.independent_pr_composition_tolerance
        )
        physical = bool(
            np.all(state.liquid_moles_lbmol > 0.0)
            and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(state.vapor_flow_lbmolph > 0.0)
            and state.distillate_lbmolph > 0.0
            and state.bottoms_lbmolph > 0.0
            and state.condenser_duty_BTUph < 0.0
            and np.all(np.diff(state.temperature_F) > 0.0)
        )
        passed = bool(
            item["success_flag"]
            and item["nfev"] <= settings.max_nfev
            and np.max(np.abs(evaluation.scaled)) < settings.residual_inf_tolerance
            and not len(item["active_bound_indices"])
            and all(j.rank == len(lower) and j.condition < settings.jacobian_condition_hard_stop for j in jacobians)
            and spectrum_change < settings.singular_value_relative_stability_tolerance
            and evaluation.component_telescoping_relative_error < settings.component_conservation_tolerance
            and evaluation.energy_telescoping_relative_error < settings.energy_conservation_tolerance
            and physical
            and phase_pass
            and item["provider_provenance"]["pass"]
            and not evaluation.clipping_or_projection_used
            and not evaluation.property_fallback_used
        )
        start_passes[name] = passed
        diagnostics[name] = {
            "spectrum_relative_change": spectrum_change,
            "physical": physical,
            "phase_pass": phase_pass,
            "tp_flash_vapor_fraction": float(flash["vapor_fraction"]),
            "independent_bubble_temperature_difference_F": float(
                bubble.temperature_F - state.temperature_F[0]
            ),
            "independent_bubble_composition_max_abs": float(
                np.max(np.abs(bubble.vapor_mole_fraction - state.bubble_vapor_mole_fraction))
            ),
            "pass": passed,
        }
    elapsed = time.perf_counter() - started
    logical_calls = sum(int(item["provider_provenance"]["total_calls"]) for item in starts.values()) + int(diagnostic_audit.report()["total_calls"])
    common_root = bool(max(agreement.values()) < settings.common_root_tolerance)
    campaign_pass = bool(
        all(start_passes.values())
        and common_root
        and diagnostic_audit.report()["pass"]
        and logical_calls < contract["limits"]["logical_provider_calls"]
        and elapsed < contract["limits"]["wall_clock_sec"]
    )
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "full_c3c4_aligned_density_root_passed" if campaign_pass else "full_c3c4_aligned_density_root_failed",
        "decision": (
            "authorize_structural_full_c3c4_dynamic_dae_contract"
            if campaign_pass else "stop_aligned_density_root_path_without_retry"
        ),
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "starts": {name: dd169._json_start(item) for name, item in starts.items()},
        "endpoint_diagnostics": diagnostics,
        "start_passes": start_passes,
        "pairwise_physical_root_agreement": agreement,
        "common_root_pass": common_root,
        "provider_routing": contract["provider_routing"],
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
    destination.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-231 Full-C3/C4 Aligned-Density Root Campaign",
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
