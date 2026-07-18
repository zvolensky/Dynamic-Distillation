#!/usr/bin/env python
"""Run the one fixed three-start DD-082 five-volume steady-root campaign."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for path in (SRC, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from audit_core_v2_gate_c_five_volume import _build_problem
from dynamic_distillation.core_v2.five_volume_residual_gate_v1 import (
    DIRECT_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
)
from dynamic_distillation.core_v2.five_volume_steady_solve_v1 import (
    FixedSteadySolveSettings,
    run_fixed_steady_solve_campaign,
)


def _finite(value: float):
    result = float(value)
    return result if np.isfinite(result) else None


def _block_maxima(evaluation, *, scaled: bool) -> dict[str, float]:
    values = evaluation.scaled if scaled else evaluation.raw
    result: dict[str, float] = {}
    for row, value in zip(evaluation.rows, values):
        result[row.block] = max(result.get(row.block, 0.0), abs(float(value)))
    return result


def _jacobian_doc(audit) -> dict:
    return {
        "step": float(audit.step),
        "rank": int(audit.rank),
        "nullity": int(audit.matrix.shape[1] - audit.rank),
        "condition": _finite(audit.condition),
        "zero_rows": list(audit.zero_rows),
        "zero_columns": list(audit.zero_columns),
        "unexpected_couplings": list(audit.unexpected_couplings),
        "colored_uncolored_max_abs": float(audit.colored_uncolored_max_abs),
        "colored_uncolored_relative": float(
            audit.colored_uncolored_relative
        ),
    }


def _attempt_doc(attempt, spec, source_profile) -> dict:
    result = {
        "start_name": attempt.start_name,
        "accepted": bool(attempt.accepted),
        "failure_reason": attempt.failure_reason,
        "solver_success": bool(attempt.solver_success),
        "solver_status": int(attempt.solver_status),
        "solver_message": attempt.solver_message,
        "iterations": int(attempt.iterations),
        "function_evaluations": int(attempt.function_evaluations),
        "jacobian_evaluations": int(attempt.jacobian_evaluations),
        "optimality": _finite(attempt.optimality),
        "cost": _finite(attempt.cost),
        "wall_clock_sec": float(attempt.wall_clock_sec),
        "active_bounds": list(attempt.active_bounds),
        "movement_by_block": attempt.movement_by_block,
        "normalized_physical_movement_max": _finite(
            attempt.normalized_physical_movement_max
        ),
        "property_call_counters": attempt.property_call_counters,
        "initial_coordinates": [
            float(value) for value in attempt.initial_coordinates
        ],
        "final_coordinates": [
            float(value) for value in attempt.final_coordinates
        ],
    }
    evaluation = attempt.evaluation
    if evaluation is None:
        result["final_state_available"] = False
        result["jacobians"] = []
        return result
    state = evaluation.state
    properties = evaluation.properties
    hydraulic_indices = [
        DIRECT_VOLUME_IDS.index(volume) for volume in HYDRAULIC_VOLUME_IDS
    ]
    residence = [
        3600.0
        * float(state.liquid_moles_lbmol[volume_index])
        / float(state.hydraulic_liquid_flow_lbmolph[hydraulic_index])
        for hydraulic_index, volume_index in enumerate(hydraulic_indices)
    ]
    final_francis = [
        float(properties.francis_flow_lbmolph[index])
        for index in hydraulic_indices
    ]
    result.update(
        {
            "final_state_available": True,
            "scaled_residual_inf_norm": float(
                np.max(np.abs(evaluation.scaled))
            ),
            "raw_residual_inf_norm": float(np.max(np.abs(evaluation.raw))),
            "scaled_block_maxima": _block_maxima(evaluation, scaled=True),
            "raw_block_maxima": _block_maxima(evaluation, scaled=False),
            "component_telescoping_error_lbmolph": [
                float(value)
                for value in evaluation.component_telescoping_error
            ],
            "component_telescoping_relative_error": float(
                evaluation.component_telescoping_relative_error
            ),
            "energy_telescoping_error_BTUph": float(
                evaluation.energy_telescoping_error_BTUph
            ),
            "energy_telescoping_relative_error": float(
                evaluation.energy_telescoping_relative_error
            ),
            "temperature_F": [
                float(value) for value in state.temperature_F
            ],
            "liquid_moles_lbmol": [
                float(value) for value in state.liquid_moles_lbmol
            ],
            "liquid_mole_fraction": [
                [float(value) for value in row]
                for row in state.liquid_mole_fraction
            ],
            "vapor_mole_fraction": [
                [float(value) for value in row]
                for row in state.vapor_mole_fraction
            ],
            "internal_energy_BTU": [
                float(value) for value in state.internal_energy_BTU
            ],
            "hydraulic_liquid_flow_lbmolph": [
                float(value)
                for value in state.hydraulic_liquid_flow_lbmolph
            ],
            "francis_flow_lbmolph": final_francis,
            "liquid_height_ft": [
                float(properties.liquid_height_ft[index])
                for index in hydraulic_indices
            ],
            "tray_spacing_ft": [
                float(geometry.tray_spacing_ft)
                for geometry in spec.hydraulic_geometry
            ],
            "over_weir_head_ft": [
                float(properties.over_weir_head_ft[index])
                for index in hydraulic_indices
            ],
            "residence_time_sec": residence,
            "distillate_lbmolph": float(state.distillate_lbmolph),
            "bottoms_lbmolph": float(state.bottoms_lbmolph),
            "source_comparison": {
                "temperature_difference_F": [
                    float(value)
                    for value in (
                        state.temperature_F
                        - np.asarray(source_profile["temperature_F"])
                    )
                ],
                "liquid_moles_difference_lbmol": [
                    float(value)
                    for value in (
                        state.liquid_moles_lbmol
                        - np.asarray(source_profile["liquid_moles_lbmol"])
                    )
                ],
                "hydraulic_flow_difference_lbmolph": [
                    float(value)
                    for value in (
                        state.hydraulic_liquid_flow_lbmolph
                        - np.asarray(
                            [
                                source_profile[
                                    "source_liquid_flow_lbmolph"
                                ][DIRECT_VOLUME_IDS.index(volume)]
                                for volume in HYDRAULIC_VOLUME_IDS
                            ]
                        )
                    )
                ],
            },
            "jacobians": [
                _jacobian_doc(audit) for audit in attempt.jacobian_audits
            ],
            "clipping_or_projection_used": bool(
                evaluation.clipping_or_projection_used
            ),
            "property_fallback_used": bool(
                evaluation.property_fallback_used
            ),
        }
    )
    return result


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-082 Core V2 Five-Volume Steady-Root Campaign",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Campaign accepted: `{report['accepted']}`",
        f"- Maximum root disagreement: "
        f"`{report['maximum_root_disagreement']}`",
        f"- Total wall clock: `{report['wall_clock_sec']:.3f} s`",
        "- Solver: `scipy.optimize.least_squares`, `method=trf`",
        "- Five-volume continuation/fallback attempted: `False`",
        "",
        "## Attempts",
        "",
        "| Start | Solver success | Residual inf | Rank | Condition | "
        "Active bounds | Accepted |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for attempt in report["attempts"]:
        jacobian = attempt["jacobians"][0] if attempt["jacobians"] else {}
        lines.append(
            f"| {attempt['start_name']} | {attempt['solver_success']} | "
            f"{attempt.get('scaled_residual_inf_norm')} | "
            f"{jacobian.get('rank')} | {jacobian.get('condition')} | "
            f"{len(attempt['active_bounds'])} | {attempt['accepted']} |"
        )
    lines.extend(
        (
            "",
            "## Pairwise Root Agreement",
            "",
        )
    )
    for pair, value in report["pairwise_root_agreement"].items():
        lines.append(f"- {pair}: `{value}`")
    lines.extend(
        (
            "",
            "## Reconciliation",
            "",
            f"- Dominant movement family: "
            f"`{report['reconciliation']['dominant_movement_family']}`",
            f"- Interpretation: {report['reconciliation']['interpretation']}",
            "",
            "## DD-058 Qualitative Reference",
            "",
            report["dd058_qualitative_reference"]["interpretation"],
            "",
            "## Decision",
            "",
            report["authorization"],
            "",
        )
    )
    return "\n".join(lines)


def run(
    workbook_path: Path,
    property_package: str,
    out_prefix: Path,
) -> dict:
    started = time.perf_counter()
    (
        _column,
        provider,
        spec,
        reference,
        source_profile,
        operating,
        _local_closures,
    ) = _build_problem(workbook_path, property_package)
    settings = FixedSteadySolveSettings()
    campaign = run_fixed_steady_solve_campaign(
        spec=spec,
        reference=reference,
        provider=provider,
        settings=settings,
    )
    attempts = [
        _attempt_doc(attempt, spec, source_profile)
        for attempt in campaign.attempts
    ]
    movement_rms: dict[str, float] = {}
    for attempt in attempts:
        for block, values in attempt["movement_by_block"].items():
            movement_rms[block] = max(
                movement_rms.get(block, 0.0),
                float(values["coordinate_rms"]),
            )
    dominant = (
        max(movement_rms, key=movement_rms.get)
        if movement_rms
        else "unavailable"
    )
    report = {
        "schema_id": "dd082-core-v2-five-volume-steady-root-campaign-v1",
        "classification": campaign.classification,
        "decision": campaign.decision,
        "accepted": bool(campaign.accepted),
        "authorization": (
            "DD-082 passes. The solved five-volume state may proceed to the "
            "predeclared short dynamic Gate C test. Gates D-G remain "
            "unauthorized."
            if campaign.accepted
            else
            "DD-082 fails the Gate C hard stop. Do not add DD-083 solver "
            "tuning, continuation, geometry changes, or another operating-"
            "specification variant. The prescribed-pressure, prescribed-"
            "vapor five-volume case has not demonstrated a common physical "
            "steady root."
        ),
        "workbook": str(workbook_path.resolve()),
        "property_package": property_package,
        "component_names": list(spec.component_names),
        "settings": asdict(settings),
        "fixed_residual_scales": [
            float(value) for value in campaign.fixed_residual_scales
        ],
        "coordinate_bounds": {
            "lower": [float(value) for value in campaign.bounds.lower],
            "upper": [float(value) for value in campaign.bounds.upper],
        },
        "start_names": list(campaign.starts),
        "smooth_seed_metadata": campaign.smooth_seed_metadata,
        "operating_parameters": operating,
        "source_profile": source_profile,
        "attempts": attempts,
        "pairwise_root_agreement": {
            name: _finite(value)
            for name, value in campaign.pairwise_root_agreement.items()
        },
        "maximum_root_disagreement": _finite(
            campaign.maximum_root_disagreement
        ),
        "reconciliation": {
            "movement_rms_by_family": movement_rms,
            "dominant_movement_family": dominant,
            "interpretation": (
                "Movement classification uses the largest transformed-"
                "coordinate RMS across the three fixed starts. It is a "
                "diagnostic, not a weighted solver objective."
            ),
        },
        "dd058_qualitative_reference": {
            "dynamic_score": 0.0848,
            "top_pressure_psia": 221.871,
            "condenser_duty_MMBTUph": -49.163,
            "distillate_lbmolph": 2254.42,
            "distillate_n_butane_mole_fraction": 0.063691,
            "interpretation": (
                "DD-058 remains a controlled v1 operational checkpoint, not "
                "equation truth for v2. DD-082 uses no DD-058 value in its "
                "residual, bounds, scales, seed construction, or acceptance."
            ),
        },
        "five_volume_nonlinear_campaign_count": 1,
        "predeclared_start_count": 3,
        "continuation_attempted": False,
        "alternate_solver_attempted": False,
        "regularization_used": False,
        "geometry_or_francis_parameter_changed": False,
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path(
            "sandbox/mini8/input/distillation_column_template_8stage.xlsx"
        ),
    )
    parser.add_argument("--property-package", default="pr")
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd082_core_v2_gate_c_steady_solve_20260718"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(args.workbook, args.property_package, args.out_prefix)
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "decision": result["decision"],
                "accepted": result["accepted"],
                "maximum_root_disagreement": result[
                    "maximum_root_disagreement"
                ],
                "wall_clock_sec": result["wall_clock_sec"],
                "attempts": [
                    {
                        "start": attempt["start_name"],
                        "solver_success": attempt["solver_success"],
                        "scaled_residual_inf_norm": attempt.get(
                            "scaled_residual_inf_norm"
                        ),
                        "accepted": attempt["accepted"],
                        "failure_reason": attempt["failure_reason"],
                    }
                    for attempt in result["attempts"]
                ],
            },
            indent=2,
        )
    )
    raise SystemExit(0 if result["accepted"] else 2)
