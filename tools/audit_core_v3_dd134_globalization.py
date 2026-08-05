#!/usr/bin/env python
"""Prepare or execute the frozen DD-135 DD-134 globalization audit."""

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

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
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
from dynamic_distillation.core_v3.newton_globalization_audit_v1 import (
    probe_newton_correction,
)


SCHEMA = "dd135-core-v3-dd134-globalization-audit-contract-v1"
RESULT_SCHEMA = "dd135-core-v3-dd134-globalization-audit-result-v1"
DD134_CONTRACT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json"
)
DD134_RESULT = Path(
    "logs/dd134_core_v3_modified_newton_short_controlled_trajectory_20260805.json"
)
CONTRACT = Path("logs/dd135_core_v3_dd134_globalization_audit_contract_20260805.json")
RESULT = Path("logs/dd135_core_v3_dd134_globalization_audit_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_135_core_v3_dd134_globalization_audit_contract_20260805.md"
)
RESULT_DOC = Path("docs/dd_135_core_v3_dd134_globalization_audit_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/newton_globalization_audit_v1.py",
    "tests/test_core_v3_newton_globalization_audit_v1.py",
    "tools/audit_core_v3_dd134_globalization.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
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


def _failure_case(name: str, rows: list[dict[str, Any]], step_seconds: float) -> dict[str, Any]:
    if len(rows) < 2 or rows[-1]["success"] or not rows[-2]["success"]:
        raise RuntimeError(f"DD-135 requires one saved terminal failure for {name}")
    previous = rows[-2]
    failed = rows[-1]
    return {
        "name": name,
        "step_seconds": float(step_seconds),
        "step_index": int(failed["index"]),
        "time_seconds": float(failed["time_seconds"]),
        "initial_coordinates": previous["final_coordinates"],
        "stalled_coordinates": failed["final_coordinates"],
        "previous_inventory_lbmol": previous["inventory_lbmol"],
        "previous_top_internal_energy_BTU": previous["top_internal_energy_BTU"],
        "previous_lower_internal_energy_BTU": previous["lower_internal_energy_BTU"],
        "previous_controller_memory": previous["controller_memory"],
        "saved_failure": {
            key: failed[key]
            for key in (
                "success",
                "iterations",
                "residual_evaluations",
                "jacobian_evaluations",
                "linear_solves",
                "rejected_line_search_steps",
                "rejected_bound_steps",
                "residual_inf_norm",
                "jacobian_rank",
                "jacobian_condition",
            )
        },
    }


def prepare() -> dict[str, Any]:
    source = _load(DD134_CONTRACT)
    result = _load(DD134_RESULT)
    if (
        result["classification"] != "dd134_failed"
        or result["decision"] != "stop_modified_newton_controlled_trajectory_path"
        or result["gates"]["solver_success"]
        or not result["gates"]["no_rebuild_fallback_retry_or_grid_change"]
    ):
        raise RuntimeError("DD-135 requires the immutable DD-134 globalization stop")
    grid = source["trajectory_grid"]
    cases = (
        _failure_case(
            "coarse",
            result["trajectories"]["coarse"],
            grid["coarse_step_seconds"],
        ),
        _failure_case(
            "refined",
            result["trajectories"]["refined"],
            grid["refined_step_seconds"],
        ),
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD134_CONTRACT, DD134_RESULT)
        },
        "source_classification": result["classification"],
        "source_decision": result["decision"],
        "failure_cases": cases,
        "line_search_fractions": source["algorithm"]["line_search_fractions"],
        "armijo_fraction": float(source["algorithm"]["armijo_fraction"]),
        "jacobian_step": float(source["jacobian_step"]),
        "required_rank": 50,
        "condition_limit": float(source["algorithm"]["condition_limit"]),
        "residual_limit": float(source["residual_limit"]),
        "saved_residual_reproduction_absolute_limit": 1.0e-10,
        "saved_condition_reproduction_relative_limit": 1.0e-6,
        "provider_call_limit": 7000,
        "wall_clock_limit_sec": 180.0,
        "classification_rules": {
            "stale_jacobian_confirmed": (
                "both stale probes reproduce no Armijo-acceptable fraction and both "
                "fresh probes provide an Armijo-acceptable fraction whose best residual "
                "is below the frozen DD-134 residual limit"
            ),
            "fresh_jacobian_not_sufficient": (
                "the audit is valid, stale failure reproduces, and at least one fresh "
                "probe cannot cross the frozen residual limit"
            ),
            "audit_invalid": "any integrity, rank, provider, call, or wall gate fails",
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-134 source or DD-135 implementation hash changes",
            "either saved failed residual or stale Jacobian condition does not reproduce",
            "either stale or fresh Jacobian loses rank or exceeds the frozen condition limit",
            "a solve is accepted, a state advances, or a trajectory or timestep is attempted",
            "a line-search fraction, bound, equation, scale, provider, or finite-difference step changes",
            "a retry, fallback, clipping, projection, or alternate solver is attempted",
            "the provider, call, or wall gate fails",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
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
                "# DD-135 Frozen DD-134 Globalization Audit Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Evidence points: saved DD-134 coarse `t=7 s` and refined `t=3 s` failures",
                "- Comparison: original root-start Jacobian versus fresh stalled-point Jacobian",
                "- Trial fractions: `1, 0.5, 0.25, 0.125`",
                "- Residual equations, scales, bounds, provider, and finite-difference step: unchanged",
                "- State acceptance, root completion, timestep, and trajectory: prohibited",
                "- Provider-call limit: `<7000`",
                "- Wall-clock limit: `<180 s`",
                "",
                "The audit distinguishes stale-Jacobian globalization loss from a residual/provider floor. It does not retry DD-134 or authorize a trajectory.",
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
        raise RuntimeError("DD-135 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-135 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-135 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-135 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _probe_record(probe) -> dict[str, Any]:
    record = asdict(probe)
    record["accepted_fractions"] = list(probe.accepted_fractions)
    record["best_residual_inf_norm"] = probe.best_residual_inf_norm
    return record


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD134_CONTRACT)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(source)
    contract = dd128._contract(source)
    pattern = controlled_terminal_step_pattern(contract)
    if pattern.shape != (50, 50):
        raise RuntimeError("DD-135 requires the frozen 50 x 50 controlled structure")
    moved_setpoints = TerminalLevelSetpoints(**source["moved_level_setpoints"])
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

        initial = np.asarray(case["initial_coordinates"], dtype=float)
        stalled = np.asarray(case["stalled_coordinates"], dtype=float)
        stalled_evaluation = objective(stalled, f"dd135:{name}:stalled_residual")
        stalled_residual = np.asarray(stalled_evaluation.scaled, dtype=float)

        def build_jacobian(point, label):
            matrix, groups = colored_central_difference_jacobian(
                lambda trial, trial_id: objective(trial, trial_id).scaled,
                point,
                pattern=pattern,
                step=float(payload["jacobian_step"]),
                state_id=f"dd135:{name}:{label}_jacobian",
            )
            if len(groups) != source["step_color_count"]:
                raise RuntimeError("DD-135 colored Jacobian group count changed")
            return matrix

        stale_jacobian = build_jacobian(initial, "stale")
        fresh_jacobian = build_jacobian(stalled, "fresh")
        probe_common = {
            "objective": objective,
            "point": stalled,
            "residual": stalled_residual,
            "line_search_fractions": payload["line_search_fractions"],
            "armijo_fraction": float(payload["armijo_fraction"]),
            "lower_bounds": lower,
            "upper_bounds": upper,
            "condition_limit": float(payload["condition_limit"]),
        }
        stale_probe = probe_newton_correction(
            jacobian=stale_jacobian,
            name=f"dd135:{name}:stale_probe",
            **probe_common,
        )
        fresh_probe = probe_newton_correction(
            jacobian=fresh_jacobian,
            name=f"dd135:{name}:fresh_probe",
            **probe_common,
        )
        records[name] = {
            "step_seconds": float(case["step_seconds"]),
            "step_index": int(case["step_index"]),
            "time_seconds": float(case["time_seconds"]),
            "saved_failure": case["saved_failure"],
            "reproduced_stalled_residual_inf_norm": float(
                np.max(np.abs(stalled_residual))
            ),
            "saved_residual_absolute_difference": abs(
                float(np.max(np.abs(stalled_residual)))
                - float(case["saved_failure"]["residual_inf_norm"])
            ),
            "stale_condition_relative_difference": abs(
                stale_probe.jacobian_condition
                - float(case["saved_failure"]["jacobian_condition"])
            )
            / float(case["saved_failure"]["jacobian_condition"]),
            "jacobian_relative_frobenius_drift": float(
                np.linalg.norm(fresh_jacobian - stale_jacobian)
                / np.linalg.norm(stale_jacobian)
            ),
            "jacobian_max_absolute_drift": float(
                np.max(np.abs(fresh_jacobian - stale_jacobian))
            ),
            "stale": _probe_record(stale_probe),
            "fresh": _probe_record(fresh_probe),
        }

    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    cases = tuple(records.values())
    integrity_gates = {
        "source_failure_preserved": all(
            not item["saved_failure"]["success"]
            and item["saved_failure"]["jacobian_evaluations"] == 1
            for item in cases
        ),
        "saved_residual_reproduced": all(
            item["saved_residual_absolute_difference"]
            < payload["saved_residual_reproduction_absolute_limit"]
            for item in cases
        ),
        "stale_condition_reproduced": all(
            item["stale_condition_relative_difference"]
            < payload["saved_condition_reproduction_relative_limit"]
            for item in cases
        ),
        "stale_and_fresh_rank": all(
            item[key]["jacobian_rank"] == payload["required_rank"]
            for item in cases
            for key in ("stale", "fresh")
        ),
        "stale_and_fresh_condition": all(
            item[key]["jacobian_condition"] < payload["condition_limit"]
            for item in cases
            for key in ("stale", "fresh")
        ),
        "stale_failure_reproduced": all(
            not item["stale"]["accepted_fractions"] for item in cases
        ),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_solve_state_advance_timestep_or_retry": True,
    }
    audit_valid = all(bool(value) for value in integrity_gates.values())
    fresh_crosses_limit = {
        name: bool(
            item["fresh"]["accepted_fractions"]
            and item["fresh"]["best_residual_inf_norm"] is not None
            and item["fresh"]["best_residual_inf_norm"] < payload["residual_limit"]
        )
        for name, item in records.items()
    }
    if not audit_valid:
        classification = "audit_invalid"
        decision = "stop_pending_audit_integrity_review"
    elif all(fresh_crosses_limit.values()):
        classification = "stale_jacobian_confirmed"
        decision = "authorize_separately_frozen_adaptive_refresh_solver_contract"
    else:
        classification = "fresh_jacobian_not_sufficient"
        decision = "stop_newton_refresh_path_and_audit_residual_provider_floor"

    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "cases": records,
        "fresh_crosses_residual_limit": fresh_crosses_limit,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": {key: bool(value) for key, value in integrity_gates.items()},
        "pass": bool(audit_valid),
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "retry_attempted": False,
        "fallback_attempted": False,
        "clipping_or_projection_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# DD-135 DD-134 Globalization Audit Result",
        "",
        f"- Classification: `{classification}`",
        f"- Decision: `{decision}`",
    ]
    for name, item in records.items():
        lines.extend(
            (
                f"- {name} stalled residual: `{item['reproduced_stalled_residual_inf_norm']:.9e}`",
                f"- {name} stale/fresh accepted fractions: `{item['stale']['accepted_fractions']}` / `{item['fresh']['accepted_fractions']}`",
                f"- {name} fresh best residual: `{item['fresh']['best_residual_inf_norm']:.9e}`",
                f"- {name} Jacobian relative drift: `{item['jacobian_relative_frobenius_drift']:.9e}`",
            )
        )
    lines.extend(
        (
            f"- DWSIM calls: `{provenance['total_calls']}`",
            f"- Wall clock: `{elapsed:.3f} s`",
            "",
            "No solve was accepted and no state, timestep, or trajectory advanced.",
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
