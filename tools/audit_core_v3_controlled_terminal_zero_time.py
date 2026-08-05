#!/usr/bin/env python
"""Prepare or execute the frozen DD-127 controlled-terminal Jacobian audit."""

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
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    LevelControllerSpecification,
    TerminalGeometry,
    build_controlled_terminal_dynamic_contract,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    controlled_terminal_zero_time_pattern,
    controlled_terminal_zero_time_variable_names,
    evaluate_controlled_terminal_zero_time,
)


SCHEMA = "dd127-core-v3-controlled-terminal-jacobian-contract-v1"
RESULT_SCHEMA = "dd127-core-v3-controlled-terminal-jacobian-result-v1"
CONTRACT = Path("logs/dd127_core_v3_controlled_terminal_jacobian_contract_20260805.json")
RESULT = Path("logs/dd127_core_v3_controlled_terminal_jacobian_20260805.json")
CONTRACT_DOC = Path("docs/dd_127_core_v3_controlled_terminal_jacobian_contract_20260805.md")
RESULT_DOC = Path("docs/dd_127_core_v3_controlled_terminal_jacobian_20260805.md")
DD124_CONTRACT = Path("logs/dd124_core_v3_controlled_terminal_zero_time_contract_20260727.json")
DD124_RESULT = Path("logs/dd124_core_v3_controlled_terminal_zero_time_20260727.json")
DD125_CONTRACT = Path("logs/dd125_core_v3_controlled_terminal_zero_time_contract_20260727.json")
DD125_RESULT = Path("logs/dd125_core_v3_controlled_terminal_zero_time_20260727.json")
DD126_RESULT = Path("logs/dd126_core_v3_controlled_terminal_zero_time_preflight_20260805.json")
DD123_RESULT = Path("logs/dd123_core_v3_controlled_terminal_dynamic_contract_20260727.json")
DD122_CONTRACT = Path("logs/dd122_core_v3_controlled_terminal_zero_rate_contract_20260727.json")
DD122_RESULT = Path("logs/dd122_core_v3_controlled_terminal_zero_rate_20260727.json")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/controlled_terminal_dynamic_contract_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_zero_time_v1.py",
    "tests/test_core_v3_controlled_terminal_zero_time_v1.py",
    "tools/audit_core_v3_controlled_terminal_zero_time.py",
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


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def _dynamic_contract(payload: Mapping[str, Any]):
    return build_controlled_terminal_dynamic_contract(
        tuple(payload["source_mapping"]["component_names"]),
        geometry=TerminalGeometry(**payload["geometry"]),
        controllers=LevelControllerSpecification(**payload["controllers"]),
    )


def prepare() -> dict[str, Any]:
    structural = _load(DD123_RESULT)
    source = _load(DD122_CONTRACT)
    root = _load(DD122_RESULT)
    aborted = _load(DD124_RESULT)
    corrected_abort = _load(DD125_RESULT)
    preflight = _load(DD126_RESULT)
    if (
        aborted["classification"] != "dd124_aborted_before_audit"
        or aborted["governed_residual_evaluated"]
        or aborted["jacobian_evaluated"]
        or aborted["timestep_attempted"]
    ):
        raise RuntimeError("DD-127 requires the immutable pre-audit DD-124 abort")
    if (
        corrected_abort["classification"]
        != "dd125_aborted_before_scientific_audit"
        or corrected_abort["scientific_gate_result"] is not None
    ):
        raise RuntimeError("DD-127 requires the immutable DD-125 interface abort")
    if (
        not preflight["pass"]
        or preflight["decision"]
        != "authorize_frozen_dd127_live_jacobian_contract"
    ):
        raise RuntimeError("DD-127 requires the passed DD-126 interface preflight")
    if (
        not structural["pass"]
        or structural["decision"]
        != "authorize_frozen_live_controlled_terminal_handoff_contract"
    ):
        raise RuntimeError("DD-127 requires the passed DD-123 authorization")
    if not root["pass"] or root["decision"] != "authorize_zero_rate_dynamic_handoff_contract":
        raise RuntimeError("DD-127 requires the accepted DD-122 root")
    contract = build_controlled_terminal_dynamic_contract(
        tuple(source["source_mapping"]["component_names"]),
        geometry=TerminalGeometry(**structural["geometry"]),
        controllers=LevelControllerSpecification(**structural["controllers"]),
    )
    pattern = controlled_terminal_zero_time_pattern(contract)
    if pattern.shape != (50, 50) or structural_rank(csr_matrix(pattern)) != 50:
        raise RuntimeError("DD-127 leading pattern is not full rank")
    endpoint = root["starts"][0]
    saved = np.asarray(endpoint["final_coordinates"], dtype=float)
    component_count = len(source["source_mapping"]["component_names"])
    state_count = 5 * component_count + 4
    base_rate_count = state_count
    algebraic = saved[state_count:-2]
    point = np.concatenate(
        (
            np.zeros(base_rate_count),
            np.zeros(2),
            algebraic,
            saved[-2:],
        )
    )
    if point.shape != (50,):
        raise RuntimeError("DD-127 zero-time coordinate reconstruction failed")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD123_RESULT,
                DD122_CONTRACT,
                DD122_RESULT,
                DD124_CONTRACT,
                DD124_RESULT,
                DD125_CONTRACT,
                DD125_RESULT,
                DD126_RESULT,
            )
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "initializer_numerical": source["initializer_numerical"],
        "top_storage_gradient_BTU_lbmol": source["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": source["pressure_link_geometry"],
        "geometry": structural["geometry"],
        "controllers": structural["controllers"],
        "inventory_lbmol": endpoint["inventory_lbmol"],
        "lower_internal_energy_BTU": endpoint["lower_internal_energy_BTU"],
        "controller_memory": _vector(saved[-2:]),
        "level_setpoints": preflight["level_setpoints"],
        "zero_time_coordinates": _vector(point),
        "expected_distillate_lbmolph": float(endpoint["distillate_lbmolph"]),
        "expected_bottoms_lbmolph": float(endpoint["bottoms_lbmolph"]),
        "variable_names": list(controlled_terminal_zero_time_variable_names(contract)),
        "row_names": [row.name for row in contract.rows],
        "structural_shape": list(pattern.shape),
        "structural_rank": int(structural_rank(csr_matrix(pattern))),
        "level_setpoint_rule": "reconstruct once from DD-122 terminal inventory divided by live DWSIM liquid density and the frozen DD-123 vessel geometry",
        "qualification_source": "DD-126 passed live residual preflight; physical level setpoints are frozen from that result",
        "jacobian_steps": list(JACOBIAN_STEPS),
        "residual_limit": 1.0e-8,
        "controller_residual_limit": 1.0e-10,
        "repeatability_limit": 1.0e-10,
        "product_reproduction_limit": 1.0e-10,
        "level_fraction_bounds": [0.01, 0.99],
        "required_rank": 50,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "colored_full_difference_limit": 1.0e-8,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "provider_call_limit": 30_000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "the DD-122 root does not remain an exact bumpless controlled zero-time state",
            "either leading Jacobian loses rank, exceeds condition, changes spectrum, or violates registered coupling",
            "a reconstructed physical level lies outside the declared vessel bounds",
            "provider ownership, conservation, call, or wall gates fail",
            "a nonlinear solve, tuning change, timestep, retry, fallback, or dynamic integration is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-127 Frozen Controlled-Terminal Jacobian Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- System: `50 x 50`, structural rank `50`",
                "- State: exact accepted DD-122 zero-rate root",
                f"- Level setpoints: `{payload['level_setpoints']}` frozen from DD-126",
                "- Controller memories: initialized from accepted stationary `D/B` outputs",
                "- Jacobians: two colored central differences and one full cross-check",
                "- Nonlinear solve, timestep, retry, or dynamics: `False`",
                "",
                "Execution is permitted once only after this exact contract is committed.",
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
        raise RuntimeError("DD-127 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-127 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-127 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-127 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-127 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _jacobian(objective, point, pattern, step, state_id):
    matrix, groups = colored_central_difference_jacobian(
        objective, point, pattern=pattern, step=step, state_id=state_id
    )
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return matrix, singular, rank, condition, len(groups)


def _full_jacobian(objective, point, step):
    matrix = np.empty((point.size, point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = step
        plus = objective(point + delta, f"dd127:full:{column}:plus")
        minus = objective(point - delta, f"dd127:full:{column}:minus")
        matrix[:, column] = (plus - minus) / (2.0 * step)
    return matrix


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(payload)
    contract = _dynamic_contract(payload)
    pattern = controlled_terminal_zero_time_pattern(contract)
    point = np.asarray(payload["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(payload["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    started = time.perf_counter()
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])

    def evaluate(candidate, state_id):
        return evaluate_controlled_terminal_zero_time(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory,
            lower_internal_energy_BTU=lower_u,
            controller_memory=memory,
            level_setpoints=setpoints,
            solve_coordinates=candidate,
            state_id=state_id,
            evaluation_kind="jacobian" if "jacobian" in state_id or "full" in state_id else "residual",
            **common,
        )

    def objective(candidate, state_id):
        return evaluate(candidate, state_id).scaled

    baseline = evaluate(point, "dd127:baseline")
    repeated = evaluate(point, "dd127:repeat")
    audits = []
    matrices = []
    for step in payload["jacobian_steps"]:
        matrix, singular, rank, condition, colors = _jacobian(
            objective, point, pattern, float(step), f"dd127:jacobian:{step:g}"
        )
        matrices.append(matrix)
        unexpected = tuple(
            f"{payload['row_names'][row]} <- {payload['variable_names'][column]}"
            for row, column in zip(
                *np.where((~pattern) & (np.abs(matrix) > payload["coupling_tolerance"]))
            )
        )
        audits.append(
            {
                "step": float(step),
                "rank": rank,
                "condition": condition,
                "singular_values": _vector(singular),
                "color_count": colors,
                "zero_rows": [payload["row_names"][i] for i in np.flatnonzero(np.max(np.abs(matrix), axis=1) <= payload["coupling_tolerance"])],
                "zero_columns": [payload["variable_names"][i] for i in np.flatnonzero(np.max(np.abs(matrix), axis=0) <= payload["coupling_tolerance"])],
                "unexpected_couplings": list(unexpected),
            }
        )
    full = _full_jacobian(objective, point, float(payload["jacobian_steps"][0]))
    full_difference = float(np.max(np.abs(matrices[0] - full)))
    full_unexpected = tuple(
        f"{payload['row_names'][row]} <- {payload['variable_names'][column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(full) > payload["coupling_tolerance"]))
        )
    )
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    physical = baseline.base.pressure_evaluation.base_evaluation.physical_state
    steady = baseline.base.pressure_evaluation.base_evaluation.steady_evaluation
    pressure = baseline.base.pressure_evaluation.pressure_psia
    densities = steady.properties.liquid_density_lbmol_ft3
    spectrum_change = _spectrum_change(
        np.asarray(audits[0]["singular_values"]),
        np.asarray(audits[1]["singular_values"]),
    )
    repeatability = float(np.max(np.abs(baseline.scaled - repeated.scaled)))
    lower_level, upper_level = payload["level_fraction_bounds"]
    product_relative_error = max(
        abs(baseline.distillate_lbmolph - payload["expected_distillate_lbmolph"])
        / payload["expected_distillate_lbmolph"],
        abs(baseline.bottoms_lbmolph - payload["expected_bottoms_lbmolph"])
        / payload["expected_bottoms_lbmolph"],
    )
    gates = {
        "residual": float(np.max(np.abs(baseline.scaled))) < payload["residual_limit"],
        "controller_residual": float(np.max(np.abs(baseline.scaled[-4:]))) < payload["controller_residual_limit"],
        "repeatability": repeatability < payload["repeatability_limit"],
        "bumpless_product_reproduction": product_relative_error < payload["product_reproduction_limit"],
        "physical_levels": bool(np.all((baseline.level_fraction > lower_level) & (baseline.level_fraction < upper_level))),
        "rank": all(item["rank"] == payload["required_rank"] for item in audits),
        "condition": all(item["condition"] < payload["condition_limit"] for item in audits),
        "spectrum": spectrum_change < payload["spectrum_change_limit"],
        "structure": all(not item["zero_rows"] and not item["zero_columns"] and not item["unexpected_couplings"] for item in audits) and not full_unexpected,
        "colored_full": full_difference < payload["colored_full_difference_limit"],
        "pressure_order": bool(np.all(np.diff(pressure) > 0.0)),
        "physical_state": bool(np.all(inventory > 0.0) and np.all(densities > 0.0) and np.all(physical.hydraulic_liquid_flow_lbmolph > 0.0) and np.all(physical.vapor_flow_lbmolph > 0.0)),
        "conservation": abs(steady.component_telescoping_relative_error) < payload["component_conservation_limit"] and abs(steady.energy_telescoping_relative_error) < payload["energy_conservation_limit"],
        "provider": provenance["pass"],
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_solve_or_timestep": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd127_passed" if passed else "dd127_failed",
        "decision": "authorize_frozen_controlled_terminal_first_step_contract" if passed else "stop_controlled_terminal_dynamic_handoff",
        "level_setpoints": asdict(setpoints),
        "liquid_density_lbmol_ft3": _vector(densities),
        "baseline_scaled_residual": _vector(baseline.scaled),
        "residual_inf_norm": float(np.max(np.abs(baseline.scaled))),
        "controller_residual_inf_norm": float(np.max(np.abs(baseline.scaled[-4:]))),
        "repeatability_inf_norm": repeatability,
        "distillate_lbmolph": baseline.distillate_lbmolph,
        "bottoms_lbmolph": baseline.bottoms_lbmolph,
        "product_relative_error": product_relative_error,
        "pressure_psia": _vector(pressure),
        "temperature_F": _vector(physical.temperature_F),
        "liquid_flow_lbmolph": _vector(physical.hydraulic_liquid_flow_lbmolph),
        "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
        "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
        "jacobians": audits,
        "spectrum_change": spectrum_change,
        "colored_full_matrix_difference": full_difference,
        "full_unexpected_couplings": list(full_unexpected),
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": passed,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "retry_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-127 Core V3 Controlled-Terminal Jacobian Audit",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Scaled residual: `{result['residual_inf_norm']:.6e}`",
                f"- Drum level setpoint: `{setpoints.drum_fraction:.6f}` fraction of diameter",
                f"- Sump level setpoint: `{setpoints.sump_fraction:.6f}` fraction of height",
                f"- Jacobian ranks: `{[item['rank'] for item in audits]}`",
                f"- Worst condition: `{max(item['condition'] for item in audits):.6e}`",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "DD-127 performed no nonlinear solve, timestep, retry, or dynamic integration.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    output = prepare() if args.mode == "prepare" else execute()
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
