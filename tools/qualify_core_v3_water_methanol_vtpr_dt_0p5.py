#!/usr/bin/env python
"""Qualify a 0.5-second nominal-feed step against two 0.25-second steps."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import core_v3_water_methanol_vtpr_dynamic_support as support  # noqa: E402


DEFAULT_JSON = Path("logs/core_v3_water_methanol_vtpr_dt_0p5_qualification_20260901.json")
DEFAULT_DOC = Path("docs/core_v3_water_methanol_vtpr_dt_0p5_qualification_20260901.md")
DEFAULT_MATRIX = Path("logs/core_v3_water_methanol_vtpr_dt_0p5_qualification_20260901.npz")
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
MATRIX_CHANGE_LIMIT = 0.05
SPECTRUM_CHANGE_LIMIT = 0.25
WALL_LIMIT_SEC = 300.0

COMPARISON_LIMITS = {
    "liquid_inventory_relative": 1.0e-6,
    "vapor_inventory_relative": 1.0e-6,
    "phase_transfer_relative": 1.0e-5,
    "temperature_absolute_F": 1.0e-5,
    "pressure_absolute_psia": 1.0e-5,
    "liquid_flow_relative": 1.0e-6,
    "vapor_flow_relative": 1.0e-6,
    "condenser_duty_relative": 1.0e-6,
    "stored_energy_relative": 1.0e-8,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _max_relative(left: np.ndarray, right: np.ndarray) -> float:
    denominator = np.maximum(np.maximum(np.abs(left), np.abs(right)), 1.0e-12)
    return float(np.max(np.abs(left - right) / denominator))


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    case = support.load_post_pulse_case()
    initial = case.post_pulse_reference
    half = support.solve_nominal_step(
        case,
        initial,
        timestep_sec=0.5,
        step_id="water_methanol:dt_qualification:half",
    )
    quarter_first = support.solve_nominal_step(
        case,
        initial,
        timestep_sec=0.25,
        step_id="water_methanol:dt_qualification:quarter_1",
    )
    quarter_reference = support.next_reference(case, quarter_first.evaluation)
    quarter_second = support.solve_nominal_step(
        case,
        quarter_reference,
        timestep_sec=0.25,
        step_id="water_methanol:dt_qualification:quarter_2",
        initial_guess=quarter_first.solution.x,
    )
    half_endpoint = half.evaluation.endpoint
    quarter_endpoint = quarter_second.evaluation.endpoint
    comparisons = {
        "liquid_inventory_relative": _max_relative(
            half_endpoint.liquid_component_inventory_lbmol,
            quarter_endpoint.liquid_component_inventory_lbmol,
        ),
        "vapor_inventory_relative": _max_relative(
            half_endpoint.vapor_component_inventory_lbmol,
            quarter_endpoint.vapor_component_inventory_lbmol,
        ),
        "phase_transfer_relative": _max_relative(
            half_endpoint.phase_transfer_lbmolph,
            quarter_endpoint.phase_transfer_lbmolph,
        ),
        "temperature_absolute_F": float(
            np.max(np.abs(half_endpoint.temperature_F - quarter_endpoint.temperature_F))
        ),
        "pressure_absolute_psia": float(
            np.max(np.abs(half_endpoint.pressure_psia - quarter_endpoint.pressure_psia))
        ),
        "liquid_flow_relative": _max_relative(
            half_endpoint.hydraulic_liquid_flow_lbmolph,
            quarter_endpoint.hydraulic_liquid_flow_lbmolph,
        ),
        "vapor_flow_relative": _max_relative(
            half_endpoint.vapor_flow_lbmolph,
            quarter_endpoint.vapor_flow_lbmolph,
        ),
        "condenser_duty_relative": abs(
            half_endpoint.condenser_duty_BTUph
            - quarter_endpoint.condenser_duty_BTUph
        )
        / max(
            abs(half_endpoint.condenser_duty_BTUph),
            abs(quarter_endpoint.condenser_duty_BTUph),
            1.0,
        ),
        "stored_energy_relative": support.relative_change(
            half.evaluation.properties.total_stored_energy_BTU,
            quarter_second.evaluation.properties.total_stored_energy_BTU,
        ),
    }
    comparison_gates = {
        name: bool(comparisons[name] < limit)
        for name, limit in COMPARISON_LIMITS.items()
    }

    matrices: list[np.ndarray] = []
    jacobian_steps: list[dict[str, Any]] = []
    for difference_step in ENDPOINT_STEPS:
        matrix, groups = support.colored_central_difference_jacobian(
            half.objective,
            half.solution.x,
            pattern=case.pattern,
            step=difference_step,
            state_id=f"water_methanol:dt_qualification:half_endpoint:h={difference_step:.1e}",
        )
        rank, condition, singular = support.rank_condition(matrix)
        matrices.append(matrix)
        jacobian_steps.append(
            {
                "step": difference_step,
                "rank": rank,
                "condition": condition,
                "singular_values": [float(value) for value in singular],
                "color_count": len(groups),
                "zero_rows": int(
                    np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)
                ),
                "zero_columns": int(
                    np.count_nonzero(np.linalg.norm(matrix, axis=0) <= 1.0e-12)
                ),
            }
        )
    spectrum_change = support.relative_change(
        np.asarray(jacobian_steps[0]["singular_values"]),
        np.asarray(jacobian_steps[1]["singular_values"]),
    )
    matrix_change = support.relative_change(matrices[0], matrices[1])
    dimension = len(case.contract.rows)
    jacobian_pass = bool(
        all(item["rank"] == dimension for item in jacobian_steps)
        and all(item["condition"] < CONDITION_LIMIT for item in jacobian_steps)
        and all(item["zero_rows"] == 0 for item in jacobian_steps)
        and all(item["zero_columns"] == 0 for item in jacobian_steps)
        and spectrum_change < SPECTRUM_CHANGE_LIMIT
        and matrix_change < MATRIX_CHANGE_LIMIT
    )
    provider_report = support.compact_provider_report(half.audit.report())
    provider_pass = bool(
        case.history_provider_report["pass"]
        and provider_report["pass"]
        and quarter_first.provider_report["pass"]
        and quarter_second.provider_report["pass"]
        and not half.audit.fallback_attempted
    )
    wall = time.perf_counter() - started
    gates = {
        "half_step": half.metrics["pass_gate"],
        "two_quarter_steps": bool(
            quarter_first.metrics["pass_gate"] and quarter_second.metrics["pass_gate"]
        ),
        "step_comparison": all(comparison_gates.values()),
        "jacobian": jacobian_pass,
        "provider": provider_pass,
        "nominal_feed": bool(
            half.gates["nominal_feed"]
            and quarter_first.gates["nominal_feed"]
            and quarter_second.gates["nominal_feed"]
        ),
        "wall": wall < WALL_LIMIT_SEC,
    }
    gates = {name: bool(value) for name, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": "core-v3-water-methanol-vtpr-dt-0p5-qualification-v1",
        "classification": (
            "nominal_feed_dt_0p5_qualified"
            if passed
            else "nominal_feed_dt_0p5_rejected"
        ),
        "decision": (
            "authorize_120_second_nominal_feed_run_at_dt_0p5"
            if passed
            else "retain_dt_0p25_and_do_not_start_long_run"
        ),
        "component_specific_logic": False,
        "feed_multiplier": 1.0,
        "starting_state": "accepted_post_pulse_state_with_feed_restored",
        "comparison": {
            "one_step_sec": 0.5,
            "reference_step_sec": 0.25,
            "reference_step_count": 2,
            "values": comparisons,
            "limits": COMPARISON_LIMITS,
            "gates": comparison_gates,
            "pass_gate": all(comparison_gates.values()),
        },
        "half_step": half.metrics,
        "quarter_steps": [quarter_first.metrics, quarter_second.metrics],
        "endpoint_jacobian": {
            "steps": jacobian_steps,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
            "pass_gate": jacobian_pass,
        },
        "provider": {
            "history": case.history_provider_report,
            "half_path": provider_report,
            "quarter_path": [
                quarter_first.provider_report,
                quarter_second.provider_report,
            ],
            "total_calls": (
                case.history_provider_calls
                + half.audit.record_count
                + quarter_first.provider_calls
                + quarter_second.provider_calls
            ),
            "pass_gate": provider_pass,
        },
        "sources": {
            str(support.SOURCE_ROOT).replace("\\", "/"): _sha256(
                support.rooted(support.SOURCE_ROOT)
            ),
            str(support.SOURCE_PULSE).replace("\\", "/"): _sha256(
                support.rooted(support.SOURCE_PULSE)
            ),
            str(support.SOURCE_PULSE_MATRIX).replace("\\", "/"): _sha256(
                support.rooted(support.SOURCE_PULSE_MATRIX)
            ),
        },
        "gates": gates,
        "wall_clock_sec": wall,
        "retry_attempted": False,
        "long_run_attempted": False,
        "pass_gate": passed,
    }
    evidence = {
        "initial_liquid_component_inventory_lbmol": (
            initial.liquid_component_inventory_lbmol
        ),
        "initial_vapor_component_inventory_lbmol": (
            initial.vapor_component_inventory_lbmol
        ),
        "initial_phase_transfer_lbmolph": initial.phase_transfer_lbmolph,
        "initial_temperature_F": initial.temperature_F,
        "initial_pressure_psia": initial.pressure_psia,
        "initial_liquid_flow_lbmolph": initial.hydraulic_liquid_flow_lbmolph,
        "initial_vapor_flow_lbmolph": initial.vapor_flow_lbmolph,
        "initial_condenser_duty_BTUph": np.asarray(
            [initial.condenser_duty_BTUph], dtype=float
        ),
        "initial_total_stored_energy_BTU": initial.total_stored_energy_BTU,
        "half_coordinates": half.solution.x,
        "quarter_coordinates": np.stack(
            [quarter_first.solution.x, quarter_second.solution.x]
        ),
        "half_liquid_component_inventory_lbmol": (
            half_endpoint.liquid_component_inventory_lbmol
        ),
        "quarter_liquid_component_inventory_lbmol": (
            quarter_endpoint.liquid_component_inventory_lbmol
        ),
        "half_vapor_component_inventory_lbmol": (
            half_endpoint.vapor_component_inventory_lbmol
        ),
        "quarter_vapor_component_inventory_lbmol": (
            quarter_endpoint.vapor_component_inventory_lbmol
        ),
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": case.pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    values = report["comparison"]["values"]
    first, second = report["endpoint_jacobian"]["steps"]
    return "\n".join(
        (
            "# Core V3 water-methanol 0.5-second timestep qualification",
            "",
            f"- Result: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            "- Feed multiplier: `1.0`",
            f"- Largest liquid/vapor inventory differences: `{values['liquid_inventory_relative']:.6e} / {values['vapor_inventory_relative']:.6e}` relative",
            f"- Largest temperature/pressure differences: `{values['temperature_absolute_F']:.6e} F / {values['pressure_absolute_psia']:.6e} psia`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            "- Retry: `False`",
            "",
            "One 0.5-second step was compared with two 0.25-second steps from the same restored-feed state.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute()
    json_path = support.rooted(args.json)
    doc_path = support.rooted(args.doc)
    matrix_path = support.rooted(args.matrix)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(matrix_path, **evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "comparison": report["comparison"]["values"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
