#!/usr/bin/env python
"""Prepare or execute the DD-162 saved-state hybrid fugacity benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    controlled_terminal_zero_time_pattern,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.hybrid_thermo_provider_v1 import (
    HybridThermoProviderV1,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_backend_factory_v1 import (
    _clapeyron_dwsim_pr_userlocations,
)
from dynamic_distillation.thermo_clapeyron_provider_v1 import (
    ThermoClapeyronProviderV1,
)


SCHEMA = "dd162-core-v3-hybrid-fugacity-benchmark-contract-v1"
RESULT_SCHEMA = "dd162-core-v3-hybrid-fugacity-benchmark-result-v1"
DD160 = Path("logs/dd160_core_v3_memoized_captured_multiminute_trajectory_contract_20260806.json")
DD161 = Path("logs/dd161_core_v3_clapeyron_provider_qualification_20260806.json")
CONTRACT = Path("logs/dd162_core_v3_hybrid_fugacity_benchmark_contract_20260806.json")
RESULT = Path("logs/dd162_core_v3_hybrid_fugacity_benchmark_20260806.json")
CONTRACT_DOC = Path("docs/dd_162_core_v3_hybrid_fugacity_benchmark_contract_20260806.md")
RESULT_DOC = Path("docs/dd_162_core_v3_hybrid_fugacity_benchmark_20260806.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/hybrid_thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/thermo_clapeyron_provider_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_zero_time_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tools/benchmark_core_v3_hybrid_fugacity.py",
)


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


def prepare() -> dict[str, Any]:
    qualification = _load(DD161)
    if (
        qualification["classification"]
        != "clapeyron_fugacity_authority_qualified_only"
        or not qualification["fugacity_acceleration_design_authorized"]
        or qualification["full_drop_in_authorized"]
    ):
        raise RuntimeError("DD-162 requires the bounded DD-161 authorization")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD160, DD161)
        },
        "provider_routing": {
            "direct_imposed_phase_fugacity": "clapeyron",
            "phase_enthalpy": "dwsim",
            "liquid_density": "dwsim",
            "vapor_compressibility_factor": "dwsim",
            "component_molecular_weights": "dwsim",
            "tp_flash_diagnostic": "dwsim",
        },
        "state": "exact DD-160 accepted zero-time controlled-terminal state",
        "residual_rows": 50,
        "solve_coordinates": 50,
        "jacobian_steps": [1.0e-5, 5.0e-6],
        "timing_repeats": 3,
        "residual_difference_limit": 2.0e-4,
        "matrix_relative_frobenius_limit": 1.0e-2,
        "singular_spectrum_relative_limit": 5.0e-2,
        "within_provider_step_change_limit": 1.0e-3,
        "condition_ratio_minimum": 0.5,
        "condition_ratio_maximum": 2.0,
        "required_rank": 50,
        "minimum_warm_matrix_speedup": 1.25,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "a DD-160/DD-161 source or DD-162 implementation hash changes",
            "any property is routed differently from the declared hybrid table",
            "a requested imposed phase falls back to stable-phase evaluation",
            "either Jacobian loses rank or exceeds the frozen stability limits",
            "hybrid warm matrix speedup is below 1.25x",
            "a nonlinear solve, timestep, state acceptance, or trajectory occurs",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-162 Frozen Hybrid Fugacity Benchmark Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- State: exact DD-160 controlled-terminal zero-time state",
                "- Comparison: complete DWSIM versus Clapeyron-fugacity/DWSIM-bulk residual and colored Jacobian",
                "- Jacobian steps: `1e-5` and `5e-6`",
                "- Minimum warm matrix speedup: `1.25x`",
                "- Nonlinear solve, timestep, or trajectory: prohibited",
                "",
                "Passing authorizes only a separately frozen hybrid root-reconstruction contract.",
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
    if claimed != actual:
        raise RuntimeError("DD-162 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-162 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-162 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-162 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _matrix_metrics(matrix: np.ndarray) -> dict[str, Any]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    cutoff = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > cutoff))
    condition = float(np.inf if singular[-1] <= cutoff else singular[0] / singular[-1])
    return {
        "rank": rank,
        "condition": condition,
        "singular_values": singular.tolist(),
    }


def _relative_frobenius(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(left)), np.finfo(float).tiny)
    return float(np.linalg.norm(right - left) / denominator)


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD160)
    spec, reference, template, _initializer, dwsim, _audit, _numerical, common = (
        dd121._context(source)
    )
    contract = dd128._contract(source)
    pattern = controlled_terminal_zero_time_pattern(contract)
    point = np.asarray(source["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(source["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(source["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(source["controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**source["original_level_setpoints"])

    case = load_case_from_excel(source["workbook"])
    column = build_column_spec_from_case(case)
    hybrid_bulk = dd121.dd102._provider(
        Path(source["workbook"]), source["property_package"]
    )
    clapeyron = ThermoClapeyronProviderV1(
        column.components_excel,
        column.components_dwsim,
        model_name="PR",
        model_kwargs=_clapeyron_dwsim_pr_userlocations(column),
    )
    clapeyron.validate_backend_available()
    hybrid = HybridThermoProviderV1(
        fugacity_provider=clapeyron,
        bulk_provider=hybrid_bulk,
    )
    dwsim_audit = ProviderCallAudit()
    hybrid_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={
            "direct_imposed_phase_fugacity": "clapeyron"
        },
    )

    def objective(provider, audit, candidate, state_id):
        evaluation = evaluate_controlled_terminal_zero_time(
            contract,
            spec,
            reference,
            template,
            provider,
            audit,
            inventory_lbmol=inventory,
            lower_internal_energy_BTU=lower_u,
            controller_memory=memory,
            level_setpoints=setpoints,
            solve_coordinates=candidate,
            state_id=state_id,
            evaluation_kind="jacobian",
            **common,
        )
        return np.asarray(evaluation.scaled, dtype=float)

    started = time.perf_counter()
    residual_dwsim = objective(dwsim, dwsim_audit, point, "dd162:dwsim:residual")
    residual_hybrid = objective(hybrid, hybrid_audit, point, "dd162:hybrid:residual")
    matrices: dict[str, dict[str, np.ndarray]] = {"dwsim": {}, "hybrid": {}}
    matrix_metrics: dict[str, dict[str, Any]] = {"dwsim": {}, "hybrid": {}}
    for name, provider, audit in (
        ("dwsim", dwsim, dwsim_audit),
        ("hybrid", hybrid, hybrid_audit),
    ):
        for step in payload["jacobian_steps"]:
            matrix, groups = colored_central_difference_jacobian(
                lambda candidate, state_id: objective(
                    provider, audit, candidate, state_id
                ),
                point,
                pattern=pattern,
                step=float(step),
                state_id=f"dd162:{name}:h_{step:g}",
            )
            key = f"{float(step):.1e}"
            matrices[name][key] = matrix
            matrix_metrics[name][key] = {
                **_matrix_metrics(matrix),
                "color_count": len(groups),
            }

    timing: dict[str, list[float]] = {"dwsim": [], "hybrid": []}
    primary_step = float(payload["jacobian_steps"][0])
    for name, provider, audit in (
        ("dwsim", dwsim, dwsim_audit),
        ("hybrid", hybrid, hybrid_audit),
    ):
        for repeat in range(int(payload["timing_repeats"])):
            matrix_started = time.perf_counter()
            colored_central_difference_jacobian(
                lambda candidate, state_id: objective(
                    provider, audit, candidate, state_id
                ),
                point,
                pattern=pattern,
                step=primary_step,
                state_id=f"dd162:{name}:timing_{repeat}",
            )
            timing[name].append(float(time.perf_counter() - matrix_started))

    primary_key = f"{primary_step:.1e}"
    secondary_key = f"{float(payload['jacobian_steps'][1]):.1e}"
    d_primary = matrices["dwsim"][primary_key]
    h_primary = matrices["hybrid"][primary_key]
    matrix_relative = _relative_frobenius(d_primary, h_primary)
    singular_d = np.asarray(matrix_metrics["dwsim"][primary_key]["singular_values"])
    singular_h = np.asarray(matrix_metrics["hybrid"][primary_key]["singular_values"])
    spectrum_relative = float(
        np.max(np.abs(singular_h - singular_d) / np.maximum(np.abs(singular_d), 1.0e-30))
    )
    within_step = {
        name: _relative_frobenius(
            matrices[name][primary_key], matrices[name][secondary_key]
        )
        for name in ("dwsim", "hybrid")
    }
    d_condition = float(matrix_metrics["dwsim"][primary_key]["condition"])
    h_condition = float(matrix_metrics["hybrid"][primary_key]["condition"])
    condition_ratio = h_condition / d_condition
    median_dwsim = float(statistics.median(timing["dwsim"]))
    median_hybrid = float(statistics.median(timing["hybrid"]))
    speedup = median_dwsim / median_hybrid
    residual_difference = float(np.max(np.abs(residual_hybrid - residual_dwsim)))
    d_report = dwsim_audit.report()
    h_report = hybrid_audit.report()
    hybrid_paths = {
        record["provider_interface"] for record in h_report["grouped_records"]
    }
    expected_paths = {
        "clapeyron.direct_imposed_phase_fugacity",
        "dwsim.declared_phase_enthalpy",
        "dwsim.declared_liquid_density",
        "dwsim.declared_vapor_compressibility_factor",
    }
    gates = {
        "source_and_shape": pattern.shape == (50, 50),
        "provider_routing": expected_paths <= hybrid_paths
        and not any(
            path.startswith("clapeyron.")
            and path != "clapeyron.direct_imposed_phase_fugacity"
            for path in hybrid_paths
        ),
        "provider_audits": bool(d_report["pass"] and h_report["pass"]),
        "residual_difference": residual_difference
        <= float(payload["residual_difference_limit"]),
        "full_rank": all(
            matrix_metrics[name][key]["rank"] == payload["required_rank"]
            for name in matrix_metrics
            for key in matrix_metrics[name]
        ),
        "matrix_relative_frobenius": matrix_relative
        <= float(payload["matrix_relative_frobenius_limit"]),
        "singular_spectrum": spectrum_relative
        <= float(payload["singular_spectrum_relative_limit"]),
        "step_stability": max(within_step.values())
        <= float(payload["within_provider_step_change_limit"]),
        "condition_ratio": float(payload["condition_ratio_minimum"])
        <= condition_ratio
        <= float(payload["condition_ratio_maximum"]),
        "meaningful_speedup": speedup
        >= float(payload["minimum_warm_matrix_speedup"]),
        "wall": (time.perf_counter() - started)
        < float(payload["wall_clock_limit_sec"]),
        "no_solve_or_dynamics": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "hybrid_fugacity_residual_jacobian_passed"
            if passed
            else "hybrid_fugacity_benchmark_failed"
        ),
        "decision": (
            "authorize_separately_frozen_hybrid_root_reconstruction_contract"
            if passed
            else "retain_full_dwsim_provider"
        ),
        "residual": {
            "dwsim_inf_norm": float(np.max(np.abs(residual_dwsim))),
            "hybrid_inf_norm": float(np.max(np.abs(residual_hybrid))),
            "max_abs_difference": residual_difference,
        },
        "matrix_metrics": matrix_metrics,
        "cross_provider": {
            "matrix_relative_frobenius": matrix_relative,
            "singular_spectrum_max_relative": spectrum_relative,
            "condition_ratio": condition_ratio,
        },
        "within_provider_step_relative_frobenius": within_step,
        "timing": {
            "dwsim_seconds": timing["dwsim"],
            "hybrid_seconds": timing["hybrid"],
            "dwsim_median_seconds": median_dwsim,
            "hybrid_median_seconds": median_hybrid,
            "speedup": speedup,
        },
        "provider_reports": {"dwsim": d_report, "hybrid": h_report},
        "gates": gates,
        "pass": bool(passed),
        "wall_clock_sec": float(time.perf_counter() - started),
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-162 Hybrid Fugacity Benchmark Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Residual maximum difference: `{residual_difference:.9e}`",
                f"- Matrix relative Frobenius difference: `{matrix_relative:.9e}`",
                f"- Singular-spectrum maximum relative difference: `{spectrum_relative:.9e}`",
                f"- Condition ratio: `{condition_ratio:.9f}`",
                f"- Warm matrix speedup: `{speedup:.6f}x`",
                f"- Gates: `{gates}`",
                "",
                "No nonlinear solve, timestep, or dynamic state advance occurred.",
                "",
            )
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    result = prepare() if args.mode == "prepare" else execute()
    return 0 if args.mode == "prepare" or result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
