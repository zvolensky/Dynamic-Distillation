#!/usr/bin/env python
"""Prepare or execute the frozen DD-099 Core V3 performance audit."""

# ruff: noqa: E402

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


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    contract_sparsity_pattern,
    greedy_column_groups,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    BackwardEulerEvaluation,
    solve_backward_euler_step,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.short_trajectory_v1 import scale_feed_throughput
from tools import run_core_v3_implicit_step as dd097


SCHEMA_ID = "dd099-core-v3-performance-contract-v1"
RESULT_SCHEMA_ID = "dd099-core-v3-performance-result-v1"
DEFAULT_DD098_CONTRACT = Path(
    "logs/dd098_core_v3_short_open_loop_contract_20260725.json"
)
DEFAULT_DD098_RESULT = Path("logs/dd098_core_v3_short_open_loop_20260725.json")
DEFAULT_CONTRACT = Path("logs/dd099_core_v3_performance_contract_20260725.json")
DEFAULT_RESULT = Path("logs/dd099_core_v3_performance_20260725.json")

FEED_FACTOR = 1.001
STEP_SECONDS = 1.0
DD098_CALLS_PER_ENDPOINT = 325332.0 / 8.0
LIMITS = {
    "scaled_residual": 1.0e-8,
    "condition": 1.0e8,
    "equilibrium_residual": 1.0e-10,
    "component_conservation": 1.0e-8,
    "energy_conservation": 1.0e-8,
    "root_component_rate_lbmolph": 1.0e-4,
    "equivalence_inventory_relative": 1.0e-7,
    "equivalence_algebraic": 1.0e-6,
    "equivalence_temperature_F": 1.0e-5,
    "equivalence_component_rate_lbmolph": 1.0e-3,
    "equivalence_jacobian_relative": 1.0e-5,
    "maximum_calls_per_solve": 10000,
    "minimum_call_reduction_from_dd098": 5.0,
}

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tests/test_core_v3_colored_jacobian_v1.py",
    "tests/test_core_v3_implicit_step_v1.py",
    "tests/test_core_v3_short_trajectory_v1.py",
    "tools/run_core_v3_performance_audit.py",
    "docs/dd_099_core_v3_performance_contract_20260725.md",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-099 Frozen Core V3 Performance Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Cases: stationary root and `+0.1%` feed throughput",
            "- Methods: uncolored and 17-color central Jacobians",
            "- Step: one independent `1.0 s` backward-Euler solve per case/method",
            "- Live property evaluation during preparation: `False`",
            "- Dynamic step during preparation: `False`",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-099 Core V3 Performance Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Numerical pass: `{payload['numerical_pass']}`",
            f"- Performance pass: `{payload['performance_pass']}`",
            f"- DD-098 calls per endpoint: `{payload['dd098_calls_per_endpoint']:.1f}`",
            f"- Mean colored calls per solve: `{payload['mean_colored_calls']:.1f}`",
            f"- Call reduction: `{payload['call_reduction_from_dd098']:.2f}x`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "",
        )
    )


def prepare(
    dd098_contract_path: Path,
    dd098_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd098_contract_path)
    result = _load(dd098_result_path)
    if not result["pass"]:
        raise RuntimeError("DD-099 requires the accepted DD-098 result")
    contract = build_dynamic_dae_contract(source["source_mapping"]["component_names"])
    pattern, names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    groups = greedy_column_groups(pattern)
    if len(groups) != 17:
        raise RuntimeError("DD-099 backward-Euler coloring changed")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd098_contract_path": str(dd098_contract_path).replace("\\", "/"),
        "dd098_contract_sha256": _sha256(ROOT / dd098_contract_path),
        "dd098_result_path": str(dd098_result_path).replace("\\", "/"),
        "dd098_result_sha256": _sha256(ROOT / dd098_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": source["solver"],
        "feed_factor": FEED_FACTOR,
        "step_seconds": STEP_SECONDS,
        "jacobian": {
            "method": "central_difference",
            "coordinate_count": len(names),
            "uncolored_evaluations": 2 * len(names),
            "color_count": len(groups),
            "colored_evaluations": 2 * len(groups),
            "groups": [list(group) for group in groups],
            "variable_names": list(names),
        },
        "dd098_calls_per_endpoint": DD098_CALLS_PER_ENDPOINT,
        "limits": LIMITS,
        "required_step_rank": 38,
        "hard_stops": [
            "colored and uncolored endpoints fail numerical equivalence",
            "any solve fails a physical, conservation, rank, or provider gate",
            "any nested bubble reconstruction occurs in the implicit residual",
            "colored provider calls are not lower than uncolored calls",
            "performance improvement is below the frozen minimum",
            "any retry, tolerance change, caching approximation, or alternate solve",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION_PATHS
        },
        "live_property_evaluation_attempted": False,
        "dynamic_step_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-099 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-099 implementation changed: {path}")
    if _sha256(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-099 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-099 result already exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-099 contract is not committed")


def _run_step(
    *,
    contract: Any,
    spec: Any,
    reference: Any,
    state: Any,
    provider: Any,
    inventory: np.ndarray,
    scales: Any,
    base_settings: Any,
    mode: str,
    name: str,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    audit = ProviderCallAudit()
    outcome = solve_backward_euler_step(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        fixed_steady_scales=scales,
        step_seconds=STEP_SECONDS,
        settings=replace(base_settings, jacobian_mode=mode),
        name=name,
    )
    report = dd097._step_report(outcome, spec, inventory, STEP_SECONDS)
    provenance = dd097._provider_summary(audit)
    provenance["nested_bubble_calls"] = sum(
        record.quantity == "bubble_temperature_and_incipient_vapor"
        for record in audit.records
    )
    return outcome, report, provenance


def _equivalence(left: Any, right: Any) -> dict[str, float]:
    if not isinstance(left.evaluation, BackwardEulerEvaluation) or not isinstance(
        right.evaluation, BackwardEulerEvaluation
    ):
        raise TypeError("DD-099 requires backward-Euler endpoints")
    a = left.evaluation
    b = right.evaluation
    jacobian_denominator = max(float(np.max(np.abs(left.jacobian))), 1.0)
    return {
        "inventory_relative": float(
            np.max(
                np.abs(a.endpoint_inventory_lbmol - b.endpoint_inventory_lbmol)
                / a.previous_inventory_lbmol
            )
        ),
        "algebraic": float(
            np.max(np.abs(a.algebraic_coordinates - b.algebraic_coordinates))
        ),
        "temperature_F": float(
            np.max(
                np.abs(
                    a.dynamic_evaluation.physical_state.temperature_F
                    - b.dynamic_evaluation.physical_state.temperature_F
                )
            )
        ),
        "component_rate_lbmolph": float(
            np.max(np.abs(a.component_rate_lbmolph - b.component_rate_lbmolph))
        ),
        "jacobian_relative": float(
            np.max(np.abs(left.jacobian - right.jacobian)) / jacobian_denominator
        ),
    }


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    source = payload["source_mapping"]
    base_spec = dd097._spec(
        source, float(payload["operating_spec"]["feed_enthalpy_BTUph"])
    )
    specs = {
        "root_hold": base_spec,
        "feed_step": scale_feed_throughput(base_spec, float(payload["feed_factor"])),
    }
    reference = dd097._reference(payload["reference"])
    state = dd097._state(payload["accepted_root_state"])
    inventory = inventory_from_state(state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-099 inventory mapping changed")
    contract = build_dynamic_dae_contract(base_spec.component_names)
    provider = dd097._provider(Path(payload["workbook"]), payload["property_package"])
    base_settings = dd097._settings(payload)
    started = time.perf_counter()
    cases: dict[str, Any] = {}
    outcomes: dict[str, dict[str, Any]] = {}
    for case_name, spec in specs.items():
        outcomes[case_name] = {}
        reports: dict[str, Any] = {}
        provenance: dict[str, Any] = {}
        for mode in ("uncolored", "colored"):
            outcome, report, provider_report = _run_step(
                contract=contract,
                spec=spec,
                reference=reference,
                state=state,
                provider=provider,
                inventory=inventory,
                scales=payload["fixed_steady_residual_scales"],
                base_settings=base_settings,
                mode=mode,
                name=f"dd099_{case_name}_{mode}",
            )
            outcomes[case_name][mode] = outcome
            reports[mode] = report
            provenance[mode] = provider_report
        equivalence = _equivalence(
            outcomes[case_name]["uncolored"], outcomes[case_name]["colored"]
        )
        cases[case_name] = {
            "reports": reports,
            "provider_provenance": provenance,
            "equivalence": equivalence,
        }
    wall_clock = float(time.perf_counter() - started)
    limits = payload["limits"]
    required_rank = int(payload["required_step_rank"])
    all_numerical_gates: list[bool] = []
    for case_name, case in cases.items():
        mode_gates = {}
        for mode, report in case["reports"].items():
            provider_report = case["provider_provenance"][mode]
            gates = {
                "success": bool(report["success"]),
                "residual": float(report["residual_inf_norm"])
                < float(limits["scaled_residual"]),
                "rank": int(report["jacobian_rank"]) == required_rank,
                "condition": float(report["jacobian_condition"])
                < float(limits["condition"]),
                "equilibrium": float(report["maximum_bubble_residual"])
                < float(limits["equilibrium_residual"]),
                "component_conservation": float(
                    report["component_conservation_relative_error"]
                )
                < float(limits["component_conservation"]),
                "energy_conservation": float(
                    report["energy_conservation_relative_error"]
                )
                < float(limits["energy_conservation"]),
                "physical": bool(report["physical_pass"]),
                "provider": bool(provider_report["pass"]),
                "no_nested_bubble": int(provider_report["nested_bubble_calls"]) == 0,
            }
            if case_name == "root_hold":
                gates["stationary"] = (
                    float(report["component_rate_max_abs_lbmolph"])
                    < float(limits["root_component_rate_lbmolph"])
                )
            mode_gates[mode] = gates
            all_numerical_gates.extend(gates.values())
        equivalence = case["equivalence"]
        equivalence_gates = {
            key: float(equivalence[key]) < float(limits[f"equivalence_{key}"])
            for key in equivalence
        }
        case["mode_gates"] = mode_gates
        case["equivalence_gates"] = equivalence_gates
        case["pass"] = all(
            [
                *equivalence_gates.values(),
                *(
                    value
                    for gates in mode_gates.values()
                    for value in gates.values()
                ),
            ]
        )
        all_numerical_gates.extend(equivalence_gates.values())
    colored_calls = [
        int(case["provider_provenance"]["colored"]["total_calls"])
        for case in cases.values()
    ]
    uncolored_calls = [
        int(case["provider_provenance"]["uncolored"]["total_calls"])
        for case in cases.values()
    ]
    mean_colored = float(np.mean(colored_calls))
    reduction = float(payload["dd098_calls_per_endpoint"]) / mean_colored
    performance_gates = {
        "colored_below_uncolored": all(
            colored < uncolored
            for colored, uncolored in zip(colored_calls, uncolored_calls, strict=True)
        ),
        "maximum_calls": max(colored_calls)
        < int(limits["maximum_calls_per_solve"]),
        "dd098_reduction": reduction
        > float(limits["minimum_call_reduction_from_dd098"]),
    }
    numerical_pass = all(all_numerical_gates)
    performance_pass = all(performance_gates.values())
    passed = numerical_pass and performance_pass
    result = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd099_performance_correction_passed"
            if passed
            else "dd099_performance_correction_failed"
        ),
        "decision": (
            "authorize_one_modest_longer_open_loop_contract"
            if passed
            else "stop_before_longer_trajectory"
        ),
        "wall_clock_sec": wall_clock,
        "jacobian": payload["jacobian"],
        "cases": cases,
        "dd098_calls_per_endpoint": float(payload["dd098_calls_per_endpoint"]),
        "colored_calls": colored_calls,
        "uncolored_calls": uncolored_calls,
        "mean_colored_calls": mean_colored,
        "call_reduction_from_dd098": reduction,
        "performance_gates": performance_gates,
        "numerical_pass": numerical_pass,
        "performance_pass": performance_pass,
        "pass": passed,
        "campaign_executed_once": True,
        "trajectory_attempted": False,
        "controller_attempted": False,
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
    parser.add_argument("--dd098-contract", type=Path, default=DEFAULT_DD098_CONTRACT)
    parser.add_argument("--dd098-result", type=Path, default=DEFAULT_DD098_RESULT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    output = (
        prepare(args.dd098_contract, args.dd098_result, args.contract)
        if args.prepare
        else execute(args.contract, args.result)
    )
    print(json.dumps(output, indent=2))
