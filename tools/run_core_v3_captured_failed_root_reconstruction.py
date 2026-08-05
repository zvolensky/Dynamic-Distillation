#!/usr/bin/env python
"""Prepare or execute DD-138 isolated captured failed-root reconstructions."""

from __future__ import annotations

import argparse
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

import audit_core_v3_captured_modified_newton as dd137
import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    solve_captured_modified_newton,
)
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings


SCHEMA = "dd138-core-v3-captured-failed-root-reconstruction-contract-v1"
RESULT_SCHEMA = "dd138-core-v3-captured-failed-root-reconstruction-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD134_RESULT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_20260805.json"
)
DD135_CONTRACT = Path("logs/dd135_core_v3_dd134_globalization_audit_contract_20260805.json")
DD135_RESULT = Path("logs/dd135_core_v3_dd134_globalization_audit_20260805.json")
DD136_RESULT = Path("logs/dd136_core_v3_dd134_residual_replay_20260805.json")
DD137_CONTRACT = Path("logs/dd137_core_v3_captured_modified_newton_contract_20260805.json")
DD137_RESULT = Path("logs/dd137_core_v3_captured_modified_newton_20260805.json")
CONTRACT = Path("logs/dd138_core_v3_captured_failed_root_reconstruction_contract_20260805.json")
RESULT = Path("logs/dd138_core_v3_captured_failed_root_reconstruction_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_138_core_v3_captured_failed_root_reconstruction_contract_20260805.md"
)
RESULT_DOC = Path("docs/dd_138_core_v3_captured_failed_root_reconstruction_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/captured_modified_newton_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "tools/audit_core_v3_captured_modified_newton.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
    "tools/run_core_v3_captured_failed_root_reconstruction.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
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
    dd137_result = _load(DD137_RESULT)
    dd135_contract = _load(DD135_CONTRACT)
    dd135_result = _load(DD135_RESULT)
    dd134_contract = _load(DD134_CONTRACT)
    if (
        not dd137_result["pass"]
        or dd137_result["classification"] != "captured_modified_newton_ready"
        or dd137_result["decision"]
        != "authorize_separately_frozen_live_in_process_failure_capture_contract"
    ):
        raise RuntimeError("DD-138 requires the immutable passed DD-137 result")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD134_CONTRACT,
                DD134_RESULT,
                DD135_CONTRACT,
                DD135_RESULT,
                DD136_RESULT,
                DD137_CONTRACT,
                DD137_RESULT,
            )
        },
        "failure_cases": dd135_contract["failure_cases"],
        "dd135_reconstructed_residual_inf_norm": {
            name: case["reproduced_stalled_residual_inf_norm"]
            for name, case in dd135_result["cases"].items()
        },
        "algorithm": dd134_contract["algorithm"],
        "jacobian_step": float(dd134_contract["jacobian_step"]),
        "required_rank": 50,
        "step_color_count": int(dd134_contract["step_color_count"]),
        "residual_limit": float(dd134_contract["residual_limit"]),
        "condition_limit": float(dd134_contract["algorithm"]["condition_limit"]),
        "identity_limit": 0.0,
        "component_conservation_limit": float(
            dd134_contract["component_conservation_limit"]
        ),
        "energy_conservation_limit": float(
            dd134_contract["energy_conservation_limit"]
        ),
        "provider_call_limit": 5000,
        "wall_clock_limit_sec": 180.0,
        "classification_rules": {
            "both_reconstructed_roots_converge": (
                "both isolated roots converge below the frozen residual limit with complete "
                "identity-clean captures"
            ),
            "captured_reconstruction_failure": (
                "at least one isolated root fails while complete identity-clean evidence is retained"
            ),
            "audit_invalid": "a source, capture, rank, physical, provider, call, or wall gate fails",
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-134 through DD-137 source or DD-138 implementation hash changes",
            "either isolated root uses other than one frozen 21-color Jacobian and one factorization",
            "a captured residual, coordinate, Jacobian, correction, or line-search trial is omitted or writeable",
            "solver and retained-evaluation identity is nonzero",
            "a fresh Jacobian, alternate solver, fallback, retry, clipping, or projection is attempted",
            "an endpoint is accepted as a simulation state or any timestep/trajectory advances",
            "a rank, condition, physical, conservation, provider, call, or wall gate fails",
        ],
        "live_property_evaluation_attempted": False,
        "live_column_residual_attempted": False,
        "live_column_jacobian_attempted": False,
        "nonlinear_root_reconstruction_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-138 Frozen Captured Failed-Root Reconstruction Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Roots: isolated DD-134 coarse `t=7 s` and refined `t=3 s` reconstructions",
                "- Solver: DD-137 captured modified Newton",
                "- Jacobian: exactly one frozen `1e-5`, 21-color matrix per root",
                "- Captured evidence: complete immutable residual/Jacobian/correction/trial vectors and final identity metrics",
                "- Fresh Jacobian, retry, fallback, clipping, projection, state acceptance, timestep, and trajectory: prohibited",
                "- Provider-call limit: `<5000`",
                "- Wall-clock limit: `<180 s`",
                "",
                "These are isolated root reconstructions only. No result may become a simulation state.",
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
        raise RuntimeError("DD-138 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-138 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-138 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-138 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD134_CONTRACT)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(source)
    contract = dd128._contract(source)
    pattern = controlled_terminal_step_pattern(contract)
    if pattern.shape != (50, 50):
        raise RuntimeError("DD-138 requires the frozen 50 x 50 structure")
    moved_setpoints = TerminalLevelSetpoints(**source["moved_level_setpoints"])
    settings = ModifiedNewtonSettings(
        **{
            key: payload["algorithm"][key]
            for key in (
                "residual_tolerance",
                "max_iterations",
                "line_search_fractions",
                "armijo_fraction",
                "condition_limit",
            )
        }
    )
    point_template = np.asarray(source["zero_time_coordinates"], dtype=float)
    lower = np.full(point_template.shape, -np.inf)
    upper = np.full(point_template.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)
    step_common = {
        "component_rate_scale_lbmolph": float(source["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "fixed_steady_scales": source["fixed_steady_residual_scales"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }
    started = time.perf_counter()
    records: dict[str, Any] = {}
    raw_outcomes = {}
    for case in payload["failure_cases"]:
        name = case["name"]

        def objective(candidate, state_id, *, _case=case):
            return evaluate_controlled_terminal_backward_euler_residual(
                contract,
                spec,
                reference,
                template,
                provider,
                call_audit,
                previous_inventory_lbmol=_case["previous_inventory_lbmol"],
                previous_top_internal_energy_BTU=_case["previous_top_internal_energy_BTU"],
                previous_lower_internal_energy_BTU=_case["previous_lower_internal_energy_BTU"],
                previous_controller_memory=_case["previous_controller_memory"],
                level_setpoints=moved_setpoints,
                solve_coordinates=candidate,
                step_seconds=float(_case["step_seconds"]),
                state_id=state_id,
                evaluation_kind="jacobian" if "jacobian" in state_id else "residual",
                **step_common,
            )

        def jacobian_builder(candidate, state_id):
            matrix, groups = colored_central_difference_jacobian(
                lambda trial, trial_id: objective(trial, trial_id).scaled,
                candidate,
                pattern=pattern,
                step=float(payload["jacobian_step"]),
                state_id=state_id,
            )
            if len(groups) != payload["step_color_count"]:
                raise RuntimeError("DD-138 color count changed")
            return matrix

        outcome = solve_captured_modified_newton(
            objective,
            jacobian_builder,
            case["initial_coordinates"],
            settings,
            lower_bounds=lower,
            upper_bounds=upper,
            name=f"dd138:{name}",
        )
        raw_outcomes[name] = outcome
        evaluation = outcome.final_evaluation
        pressure_evaluation = evaluation.base.dae_evaluation.pressure_evaluation
        physical = pressure_evaluation.base_evaluation.physical_state
        steady = pressure_evaluation.base_evaluation.steady_evaluation
        stalled = np.asarray(case["stalled_coordinates"], dtype=float)
        record = dd137._record(outcome)
        record.update(
            {
                "source_step_seconds": float(case["step_seconds"]),
                "source_step_index": int(case["step_index"]),
                "source_dd134_residual_inf_norm": float(
                    case["saved_failure"]["residual_inf_norm"]
                ),
                "dd135_reconstructed_residual_inf_norm": float(
                    payload["dd135_reconstructed_residual_inf_norm"][name]
                ),
                "final_vs_dd135_stalled_coordinate_relative": float(
                    np.max(
                        np.abs(outcome.final_coordinates - stalled)
                        / np.maximum(np.abs(stalled), 1.0)
                    )
                ),
                "level_fraction": evaluation.level_fraction.tolist(),
                "distillate_lbmolph": float(evaluation.distillate_lbmolph),
                "bottoms_lbmolph": float(evaluation.bottoms_lbmolph),
                "pressure_psia": pressure_evaluation.pressure_psia.tolist(),
                "minimum_inventory_lbmol": float(
                    np.min(evaluation.base.endpoint_inventory_lbmol)
                ),
                "minimum_liquid_flow_lbmolph": float(
                    np.min(physical.hydraulic_liquid_flow_lbmolph)
                ),
                "minimum_vapor_flow_lbmolph": float(
                    np.min(physical.vapor_flow_lbmolph)
                ),
                "component_conservation_relative": float(
                    steady.component_telescoping_relative_error
                ),
                "energy_conservation_relative": float(
                    steady.energy_telescoping_relative_error
                ),
            }
        )
        records[name] = record
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    capture_complete = all(
        outcome.frozen_jacobian is not None
        and outcome.jacobian_evaluations == 1
        and outcome.linear_solves == len(outcome.iteration_captures)
        and outcome.residual_evaluations
        == 1
        + sum(
            trial.within_bounds
            for iteration in outcome.iteration_captures
            for trial in iteration.trials
        )
        and records[name]["all_capture_arrays_read_only"]
        for name, outcome in raw_outcomes.items()
    )
    identity_clean = all(
        outcome.final_residual_vs_evaluation_max_abs <= payload["identity_limit"]
        and outcome.final_coordinates_vs_evaluation_max_abs <= payload["identity_limit"]
        for outcome in raw_outcomes.values()
    )
    gates = {
        "capture_complete": bool(capture_complete),
        "solver_evaluation_identity": bool(identity_clean),
        "rank": all(
            outcome.jacobian_rank == payload["required_rank"]
            for outcome in raw_outcomes.values()
        ),
        "condition": all(
            outcome.jacobian_condition < payload["condition_limit"]
            for outcome in raw_outcomes.values()
        ),
        "pressure_order": all(
            np.all(np.diff(record["pressure_psia"]) > 0.0)
            for record in records.values()
        ),
        "physical": all(
            record["minimum_inventory_lbmol"] > 0.0
            and record["minimum_liquid_flow_lbmolph"] > 0.0
            and record["minimum_vapor_flow_lbmolph"] > 0.0
            and np.all(
                (np.asarray(record["level_fraction"]) > 0.01)
                & (np.asarray(record["level_fraction"]) < 0.99)
            )
            for record in records.values()
        ),
        "conservation": all(
            abs(record["component_conservation_relative"])
            < payload["component_conservation_limit"]
            and abs(record["energy_conservation_relative"])
            < payload["energy_conservation_limit"]
            for record in records.values()
        ),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_fresh_jacobian_retry_or_state_advance": True,
    }
    audit_valid = all(bool(value) for value in gates.values())
    both_converged = all(
        outcome.success and outcome.final_residual_inf_norm < payload["residual_limit"]
        for outcome in raw_outcomes.values()
    )
    if not audit_valid:
        classification = "audit_invalid"
        decision = "stop_pending_capture_integrity_review"
    elif both_converged:
        classification = "both_reconstructed_roots_converge"
        decision = "authorize_separately_frozen_captured_short_trajectory_contract"
    else:
        classification = "captured_reconstruction_failure"
        decision = "authorize_static_captured_failure_adjudication_only"
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "outcomes": records,
        "both_converged": bool(both_converged),
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(audit_valid),
        "fresh_jacobian_attempted": False,
        "retry_attempted": False,
        "fallback_attempted": False,
        "clipping_or_projection_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# DD-138 Captured Failed-Root Reconstruction Result",
        "",
        f"- Classification: `{classification}`",
        f"- Decision: `{decision}`",
    ]
    for name, outcome in raw_outcomes.items():
        record = records[name]
        lines.extend(
            (
                f"- {name} success/residual: `{outcome.success}` / `{outcome.final_residual_inf_norm:.9e}`",
                f"- {name} iterations/trials: `{outcome.iterations}` / `{sum(len(item.trials) for item in outcome.iteration_captures)}`",
                f"- {name} rank/condition: `{outcome.jacobian_rank}` / `{outcome.jacobian_condition:.9e}`",
                f"- {name} final vs DD-135 stalled coordinate: `{record['final_vs_dd135_stalled_coordinate_relative']:.9e}`",
                f"- {name} residual/coordinate identity: `{outcome.final_residual_vs_evaluation_max_abs:.1e}` / `{outcome.final_coordinates_vs_evaluation_max_abs:.1e}`",
            )
        )
    lines.extend(
        (
            f"- DWSIM calls: `{provenance['total_calls']}`",
            f"- Wall clock: `{elapsed:.3f} s`",
            "",
            "No reconstructed endpoint was accepted as a simulation state; no timestep or trajectory advanced.",
            "",
        )
    )
    (ROOT / RESULT_DOC).write_text("\n".join(lines), encoding="utf-8")
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
