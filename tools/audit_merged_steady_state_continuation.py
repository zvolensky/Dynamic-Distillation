#!/usr/bin/env python
"""Run the structural-only DD-074 merged-continuation authorization gate."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.direct_steady_state_continuation_v1 import (
    DD074_STATE_SCHEMA,
    SmoothPhysicalCoordinates,
    audit_merged_continuation_structure,
    build_merged_continuation_stages,
    evaluate_stage_homotopy,
)
from dynamic_distillation.direct_steady_state_registry_v1 import (
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    build_chemsep_guess,
    build_direct_steady_state_problem,
    evaluate_direct_steady_state_residual,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_relative_volatility_provider_v1 import (
    RelativeVolatilityThermoProviderV1,
)


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-074 Merged Continuation Structural Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Structural gate passed: `{report['pass_gate']}`",
        f"- Live solve attempted: `{report['live_solve_attempted']}`",
        f"- Live solve authorized: `{report['live_solve_authorized']}`",
        "",
        "## Stage Structure",
        "",
        "| Stage | Name | Size | Physical rank | Nullity | Empty rows | Unused columns | Identity anchors | Pass |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for stage in report["structure"]["stages"]:
        lines.append(
            f"| {stage['number']} | {stage['name']} | "
            f"{stage['unknown_count']} | {stage['physical_structural_rank']} | "
            f"{stage['physical_structural_nullity']} | "
            f"{len(stage['empty_residuals'])} | "
            f"{len(stage['unused_unknowns'])} | "
            f"{stage['variable_identity_anchors']} | {stage['pass_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Merged Block Accounting",
            "",
        ]
    )
    for block, count in report["merged_residual_counts"].items():
        lines.append(f"- `{block}`: `{count}`")
    lines.extend(
        [
            "",
            "The DD-071 registry supplies `60` local equilibrium rows. The "
            "merged block is `160` local rows plus `80` steady-balance rows; "
            "no equations are added to reach `240`.",
            "",
            "## Endpoint And Conservation Checks",
            "",
            f"- Lambda-zero identity error: "
            f"`{report['endpoint_checks']['lambda_zero_identity_max_error']:.6g}`",
            f"- Merged lambda-one DD-072 identity error: "
            f"`{report['endpoint_checks']['merged_lambda_one_max_error']:.6g}`",
            f"- Final lambda-one DD-072 identity error: "
            f"`{report['endpoint_checks']['final_lambda_one_max_error']:.6g}`",
            f"- Component telescoping: "
            f"`{report['endpoint_checks']['component_conservation_pass']}`",
            f"- Energy telescoping: "
            f"`{report['endpoint_checks']['energy_conservation_pass']}`",
            "",
            "## Structural Stop",
            "",
            f"- Unmatched unknown: "
            f"`{', '.join(report['structure']['stages'][0]['unmatched_unknowns'])}`",
            f"- Unmatched residual: "
            f"`{', '.join(report['structure']['stages'][0]['unmatched_residuals'])}`",
            "",
            report["decision"],
            "",
            "Per the predefined DD-074 hard stop, no live DWSIM solve was run "
            "and manual release-order continuation is retired.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    column = build_column_spec_from_case(load_case_from_excel(args.excel))
    active_stages = tuple(
        int(stage)
        for stage in column.stage_1based
        if int(stage)
        not in (int(column.stage_1based[0]), int(column.stage_1based[-1]))
    )
    registry = combine_reboiler_and_sump_registry(
        build_direct_steady_state_registry(
            component_names=column.components_excel,
            active_stage_ids=active_stages,
        )
    )
    provider = RelativeVolatilityThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        alpha_light=1.6,
    )
    problem = build_direct_steady_state_problem(
        registry=registry,
        column=column,
        provider=provider,
        bottoms_light_key_target=args.bottoms_light_key_target,
    )
    stages = build_merged_continuation_stages(problem)
    structure = audit_merged_continuation_structure(problem)
    guess = build_chemsep_guess(problem)
    direct = evaluate_direct_steady_state_residual(problem, guess)
    coordinates = SmoothPhysicalCoordinates(
        problem, guess, direct.variable_scales
    )

    first = stages[0]
    first_coordinates = coordinates.encode(guess, first.unknown_indices)
    zero = evaluate_stage_homotopy(
        problem,
        first,
        coordinates,
        first_coordinates,
        0.0,
        direct.residual_scales,
    )
    first_endpoint = evaluate_stage_homotopy(
        problem,
        first,
        coordinates,
        first_coordinates,
        1.0,
        direct.residual_scales,
    )
    final = stages[-1]
    final_coordinates = coordinates.encode(guess, final.unknown_indices)
    final_endpoint = evaluate_stage_homotopy(
        problem,
        final,
        coordinates,
        final_coordinates,
        1.0,
        direct.residual_scales,
    )
    expected_first = (
        direct.raw[list(first.residual_indices)]
        / direct.residual_scales[list(first.residual_indices)]
    )
    expected_final = direct.raw / direct.residual_scales
    merged_counts = Counter(
        registry.residuals[index].block for index in first.residual_indices
    )

    pass_gate = bool(
        structure.pass_gate
        and np.array_equal(zero.vector, first_coordinates)
        and np.array_equal(first_endpoint.vector, expected_first)
        and np.array_equal(final_endpoint.vector, expected_final)
        and direct.conservation.component_pass
        and direct.conservation.energy_pass
    )
    classification = (
        "dd074_structural_gate_passed"
        if pass_gate
        else "dd074_structural_gate_failed_manual_continuation_retired"
    )
    decision = (
        "DD-074 passes; one bounded live merged-stage attempt is authorized."
        if pass_gate
        else (
            "DD-074 fails before a live solve. The merged 240 x 240 physical "
            "block has structural rank 239 and nullity 1. Under the predefined "
            "hard stop, retire manual staged continuation and pivot architectures."
        )
    )
    report = {
        "classification": classification,
        "pass_gate": pass_gate,
        "decision": decision,
        "excel_path": str(Path(args.excel).resolve()),
        "state_schema": DD074_STATE_SCHEMA,
        "structure": {
            **asdict(structure),
            "stages": [asdict(stage) for stage in structure.stages],
        },
        "merged_unknown_counts": dict(
            sorted(
                Counter(
                    registry.unknowns[index].block
                    for index in first.unknown_indices
                ).items()
            )
        ),
        "merged_residual_counts": dict(sorted(merged_counts.items())),
        "endpoint_checks": {
            "lambda_zero_identity_max_error": float(
                np.max(np.abs(zero.vector - first_coordinates))
            ),
            "merged_lambda_one_max_error": float(
                np.max(np.abs(first_endpoint.vector - expected_first))
            ),
            "final_lambda_one_max_error": float(
                np.max(np.abs(final_endpoint.vector - expected_final))
            ),
            "component_conservation_pass": direct.conservation.component_pass,
            "component_relative_error": (
                direct.conservation.component_relative_error.tolist()
            ),
            "energy_conservation_pass": direct.conservation.energy_pass,
            "energy_relative_error": direct.conservation.energy_relative_error,
        },
        "live_solve_authorized": pass_gate,
        "live_solve_attempted": False,
    }
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report), encoding="utf-8"
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", required=True)
    parser.add_argument("--bottoms-light-key-target", type=float, default=0.04717)
    parser.add_argument(
        "--out-prefix",
        default=r"logs\direct_steady_state_merged_structure_20260718",
    )
    return parser


if __name__ == "__main__":
    result = run(_parser().parse_args())
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "pass_gate": result["pass_gate"],
                "stage_sizes": result["structure"]["actual_sizes"],
                "stage_ranks": [
                    stage["physical_structural_rank"]
                    for stage in result["structure"]["stages"]
                ],
                "live_solve_attempted": result["live_solve_attempted"],
                "decision": result["decision"],
            },
            indent=2,
        )
    )
