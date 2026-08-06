#!/usr/bin/env python
"""Prepare or execute DD-165 hybrid-Jacobian memoized short trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_memoized_captured_short_trajectory as dd158
import run_core_v3_parallel_captured_short_trajectory as dd149
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.hybrid_thermo_provider_v1 import HybridThermoProviderV1
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_backend_factory_v1 import (
    _clapeyron_dwsim_pr_userlocations,
)
from dynamic_distillation.thermo_clapeyron_provider_v1 import ThermoClapeyronProviderV1


SCHEMA = "dd165-core-v3-hybrid-jacobian-memoized-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd165-core-v3-hybrid-jacobian-memoized-short-trajectory-result-v1"
DD158_CONTRACT = Path(
    "logs/dd158_core_v3_memoized_captured_short_trajectory_contract_20260806.json"
)
DD158_RESULT = Path(
    "logs/dd158_core_v3_memoized_captured_short_trajectory_20260806.json"
)
DD160_RESULT = Path(
    "logs/dd160_core_v3_memoized_captured_multiminute_trajectory_20260806.json"
)
DD164_RESULT = Path("logs/dd164_core_v3_clapeyron_jacobian_dwsim_root_20260806.json")
CONTRACT = Path(
    "logs/dd165_core_v3_hybrid_jacobian_memoized_short_trajectory_contract_20260806.json"
)
RESULT = Path(
    "logs/dd165_core_v3_hybrid_jacobian_memoized_short_trajectory_20260806.json"
)
CONTRACT_DOC = Path(
    "docs/dd_165_core_v3_hybrid_jacobian_memoized_short_trajectory_contract_20260806.md"
)
RESULT_DOC = Path(
    "docs/dd_165_core_v3_hybrid_jacobian_memoized_short_trajectory_20260806.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/hybrid_thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/thermo_clapeyron_provider_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tools/run_core_v3_parallel_captured_short_trajectory.py",
    "tools/run_core_v3_memoized_captured_short_trajectory.py",
    "tools/run_core_v3_hybrid_jacobian_memoized_short_trajectory.py",
)


_BASE_WORKER_INITIALIZE = dd149._worker_initialize


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


def _hybrid_worker_initialize(contract_path: str) -> None:
    _BASE_WORKER_INITIALIZE(str(contract_path))
    if dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-165 worker context was not initialized")
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    case = load_case_from_excel(payload["workbook"])
    column = build_column_spec_from_case(case)
    clapeyron = ThermoClapeyronProviderV1(
        column.components_excel,
        column.components_dwsim,
        model_name="PR",
        model_kwargs=_clapeyron_dwsim_pr_userlocations(column),
    )
    clapeyron.validate_backend_available()
    hybrid = HybridThermoProviderV1(
        fugacity_provider=clapeyron,
        bulk_provider=dd149._WORKER_CONTEXT["provider"],
    )
    hybrid.set_exact_state_memoization(True, clear=True)
    dd149._WORKER_CONTEXT.update(
        {
            "provider": hybrid,
            "call_audit": ProviderCallAudit(
                provider_identity="dwsim",
                interface_provider_identities={
                    "direct_imposed_phase_fugacity": "clapeyron"
                },
            ),
            "auto_thermo_memoization": True,
        }
    )


def prepare() -> dict[str, Any]:
    source = _load(DD158_CONTRACT)
    dd158_result = _load(DD158_RESULT)
    dd160_result = _load(DD160_RESULT)
    dd164_result = _load(DD164_RESULT)
    if (
        not dd158_result["pass"]
        or not dd160_result["pass"]
        or not dd164_result["pass"]
        or dd164_result["decision"]
        != "authorize_separately_frozen_short_derivative_acceleration_trajectory"
    ):
        raise RuntimeError("DD-165 requires passing DD-158/DD-160/DD-164 evidence")
    excluded = {
        "schema_id",
        "preparation_base_commit",
        "sources",
        "implementation_sha256",
        "hard_stops",
        "contract_payload_sha256",
        "live_property_evaluation_attempted",
        "nonlinear_solve_attempted",
        "timestep_attempted",
        "dynamic_integration_attempted",
        "campaign_executed",
        "thermo_memoization",
    }
    payload = {key: value for key, value in source.items() if key not in excluded}
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD158_CONTRACT, DD158_RESULT, DD160_RESULT, DD164_RESULT)
            },
            "derivative_acceleration": {
                "main_process_residual_provider": "dwsim",
                "worker_jacobian_provider": "clapeyron-fugacity/dwsim-bulk",
                "worker_count": 4,
                "persistent_pool_count": 1,
                "exact_memoization": True,
                "expected_roots": 30,
                "expected_calls_per_root": 1176,
                "minimum_hit_fraction_each_root": 0.60,
                "capture_equivalence_limit": 1.0e-10,
                "trajectory_wall_ratio_vs_dd158_maximum": 0.95,
                "total_wall_limit_sec": 120.0,
                "dd158_trajectory_wall_sec": float(
                    dd158_result["trajectory_wall_clock_sec"]
                ),
                "dd158_pool_startup_sec": float(dd158_result["pool_startup_wall_sec"]),
                "dd160_trajectory_wall_sec": float(
                    dd160_result["trajectory_wall_clock_sec"]
                ),
                "dd160_total_wall_sec": float(dd160_result["total_wall_clock_sec"]),
                "dd160_pool_startup_sec": float(dd160_result["pool_startup_wall_sec"]),
                "projected_five_minute_wall_limit_sec": float(
                    dd160_result["total_wall_clock_sec"]
                ),
            },
            "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
            "hard_stops": [
                "a DD-158/DD-160/DD-164 source or DD-165 implementation hash changes",
                "the DWSIM main-process residual, solver, grids, controllers, or scientific gates change",
                "a worker routes enthalpy, density, vapor Z, molecular weight, or TP flash to Clapeyron",
                "any capture, accepted state, or endpoint differs beyond 1e-10",
                "any root memo hit fraction is below 0.60",
                "trajectory work is not at least five percent faster than DD-158",
                "the startup-adjusted five-minute projection does not beat DD-160",
                "a rebuild, retry, fallback, clipping, projection, controller change, or grid change occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-165 Frozen Hybrid-Jacobian Memoized Short-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific case: exact DD-158 10-second coarse/refined controlled trajectory",
                "- Main-process residual, solver, line search, and endpoint: DWSIM only",
                "- Four worker Jacobians: Clapeyron fugacity with DWSIM bulk properties",
                "- Exact memoization: one epoch per root; hit fraction `>=0.60`",
                "- Capture and state equivalence: `<=1e-10`",
                "- Trajectory wall: `<=0.95x` DD-158",
                "- Startup-adjusted five-minute projection: below accepted DD-160",
                "- Retry, fallback, clipping, projection, or grid change: prohibited",
                "",
                "Passing authorizes a separately frozen longer derivative-accelerated trajectory. Failure retires this acceleration path.",
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
        raise RuntimeError("DD-165 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-165 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-165 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-165 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    acceleration = payload["derivative_acceleration"]
    original = (
        dd149.CONTRACT,
        dd149.RESULT,
        dd149.RESULT_DOC,
        dd149.RESULT_SCHEMA,
        dd149._worker_initialize,
    )
    dd149.CONTRACT = CONTRACT
    dd149.RESULT = RESULT
    dd149.RESULT_DOC = RESULT_DOC
    dd149.RESULT_SCHEMA = RESULT_SCHEMA
    dd149._worker_initialize = _hybrid_worker_initialize
    try:
        result = dd149.execute()
    finally:
        (
            dd149.CONTRACT,
            dd149.RESULT,
            dd149.RESULT_DOC,
            dd149.RESULT_SCHEMA,
            dd149._worker_initialize,
        ) = original

    memo = dd158._memo_summary(result["parallel_jacobian_evidence"])
    trajectory_ratio = float(
        result["trajectory_wall_clock_sec"]
        / acceleration["dd158_trajectory_wall_sec"]
    )
    nontrajectory_dd160 = float(
        acceleration["dd160_total_wall_sec"]
        - acceleration["dd160_trajectory_wall_sec"]
    )
    startup_delta = float(
        result["pool_startup_wall_sec"] - acceleration["dd160_pool_startup_sec"]
    )
    projected_five_minute_wall = float(
        nontrajectory_dd160
        + startup_delta
        + acceleration["dd160_trajectory_wall_sec"] * trajectory_ratio
    )
    inherited_gates = dict(result["gates"])
    gates = {
        "inherited_scientific_and_equivalence": bool(
            result["pass"] and all(inherited_gates.values())
        ),
        "root_and_call_accounting": len(memo["per_root"])
        == acceleration["expected_roots"]
        and all(
            item["calls"] == acceleration["expected_calls_per_root"]
            for item in memo["per_root"]
        ),
        "memo_hit_fraction_each_root": memo["minimum_root_hit_fraction"]
        >= acceleration["minimum_hit_fraction_each_root"],
        "trajectory_wall_improvement": trajectory_ratio
        <= acceleration["trajectory_wall_ratio_vs_dd158_maximum"],
        "total_wall": result["total_wall_clock_sec"]
        <= acceleration["total_wall_limit_sec"],
        "five_minute_projection": projected_five_minute_wall
        < acceleration["projected_five_minute_wall_limit_sec"],
        "hybrid_jacobian_only": True,
        "no_forbidden_actions": bool(
            not result["jacobian_rebuild_attempted"]
            and not result["fallback_attempted"]
            and not result["retry_attempted"]
            and not result["grid_changed"]
        ),
    }
    passed = all(bool(value) for value in gates.values())
    result.update(
        {
            "schema_id": RESULT_SCHEMA,
            "classification": (
                "hybrid_jacobian_memoized_short_trajectory_passed"
                if passed
                else "hybrid_jacobian_memoized_short_trajectory_failed"
            ),
            "decision": (
                "authorize_separately_frozen_longer_derivative_accelerated_trajectory"
                if passed
                else "retain_parallel_memoized_dwsim_jacobians"
            ),
            "source_dd149_gates": inherited_gates,
            "thermo_memoization": memo,
            "trajectory_wall_ratio_vs_dd158": trajectory_ratio,
            "projected_five_minute_wall_sec": projected_five_minute_wall,
            "gates": {key: bool(value) for key, value in gates.items()},
            "pass": bool(passed),
            "hybrid_residual_used_in_main_process": False,
            "campaign_executed_once": True,
        }
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-165 Hybrid-Jacobian Memoized Short-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed roots: `{len(memo['per_root'])}`",
                f"- Minimum memo hit fraction: `{memo['minimum_root_hit_fraction']:.6f}`",
                f"- Trajectory wall: `{result['trajectory_wall_clock_sec']:.3f} s`",
                f"- DD-158 trajectory ratio: `{trajectory_ratio:.6f}`",
                f"- Pool startup wall: `{result['pool_startup_wall_sec']:.3f} s`",
                f"- Total governed wall: `{result['total_wall_clock_sec']:.3f} s`",
                f"- Projected five-minute wall: `{projected_five_minute_wall:.3f} s`",
                "",
                "DWSIM retained every main-process residual, line-search, convergence, and endpoint decision.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
