#!/usr/bin/env python
"""Run the one permitted five-volume conserved-equation feasibility study."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.reduced_column_feasibility_v1 import (
    FixedSolverSettings,
    build_reduced_feasibility_case,
    run_reduced_feasibility_study,
)
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


def _jsonable_numerical_audit(audit: Any) -> dict[str, Any]:
    result = asdict(audit)
    result.pop("matrix", None)
    return result


def _jsonable_attempt(attempt: Any) -> dict[str, Any]:
    result = asdict(attempt)
    result.pop("final_vector", None)
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DD-075 Reduced-Column Feasibility Study",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Accepted: `{report['accepted']}`",
        f"- Numerical authorization gate: `{report['numerical_gate_pass']}`",
        f"- Elapsed wall time: `{report['elapsed_wall_sec']:.3f} s`",
        f"- Thermo: `{report['thermo_backend']}`",
        "",
        "## Reduced Topology",
        "",
        "| Reduced stage | Physical role | Source stage |",
        "|---:|---|---:|",
    ]
    mapping = report["mapping"]
    for reduced, role, source in zip(
        mapping["reduced_stage_1based"],
        mapping["role_by_reduced_stage"],
        mapping["source_stage_1based"],
    ):
        lines.append(f"| {reduced} | {role} | {source} |")
    structure = report["structure"]
    lines.extend(
        [
            "",
            "## Structural Gate",
            "",
            f"- Unknowns/equations: `{structure['unknown_count']} / "
            f"{structure['residual_count']}`",
            f"- Structural rank/nullity: `{structure['structural_rank']} / "
            f"{structure['structural_nullity']}`",
            f"- Gate passed: `{structure['pass_gate']}`",
            "",
            "## Initial Numerical Gate",
            "",
            "| Seed/audit | Rank | Nullity | Condition | Empty rows | Empty columns |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, audit in report["initial_numerical_audits"]:
        lines.append(
            f"| {name} | {audit['rank']} | {audit['nullity']} | "
            f"{audit['condition_estimate']:.6g} | "
            f"{len(audit['near_zero_rows'])} | "
            f"{len(audit['near_zero_columns'])} |"
        )
    lines.extend(
        [
            "",
            "## Fixed Solver Attempts",
            "",
            "| Method | Seed | Accepted | Residual inf | Rank | Condition | Iterations | Evaluations |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    if report["attempts"]:
        for attempt in report["attempts"]:
            lines.append(
                f"| {attempt['method']} | {attempt['seed_name']} | "
                f"{attempt['accepted']} | "
                f"{attempt['final_scaled_inf_norm']:.6g} | "
                f"{attempt['numerical_rank']} | "
                f"{attempt['condition_estimate']:.6g} | "
                f"{attempt['iterations']} | "
                f"{attempt['function_evaluations']} |"
            )
    else:
        lines.append(
            "| not authorized | - | False | - | - | - | - | - |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            report["decision"],
            "",
            "This is the sole reduced topology and fixed solver recipe. A failed "
            "result does not authorize a tray-count ladder, equation-block "
            "removal, profile forcing, clipping, or post-run parameter tuning.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    column = build_column_spec_from_case(load_case_from_excel(args.excel))
    provider = ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=args.dwsim_property_package,
    )
    case = build_reduced_feasibility_case(
        column=column,
        provider=provider,
        bottoms_light_key_target=args.bottoms_light_key_target,
    )
    settings = FixedSolverSettings()
    study = run_reduced_feasibility_study(case, settings=settings)
    elapsed = time.perf_counter() - started

    matrices = {
        f"initial_jacobian__{name}": audit.matrix
        for name, audit in study.initial_numerical_audits
    }
    matrices.update(
        {
            f"final_vector__{attempt.method}__{attempt.seed_name}": (
                attempt.final_vector
            )
            for attempt in study.attempts
        }
    )
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_prefix.with_suffix(".npz"), **matrices)

    report = {
        "schema_id": study.schema_id,
        "classification": study.classification,
        "accepted": study.accepted,
        "decision": study.decision,
        "excel_path": str(Path(args.excel).resolve()),
        "thermo_backend": f"DWSIM {args.dwsim_property_package.upper()}",
        "elapsed_wall_sec": float(elapsed),
        "settings": asdict(settings),
        "mapping": asdict(study.mapping),
        "structure": asdict(study.structure),
        "initial_numerical_audits": [
            [name, _jsonable_numerical_audit(audit)]
            for name, audit in study.initial_numerical_audits
        ],
        "numerical_gate_pass": study.numerical_gate_pass,
        "attempts": [
            _jsonable_attempt(attempt) for attempt in study.attempts
        ],
        "root_agreement_max_scaled_difference": (
            study.root_agreement_max_scaled_difference
        ),
        "artifacts": {
            "json": str(output_prefix.with_suffix(".json").resolve()),
            "markdown": str(output_prefix.with_suffix(".md").resolve()),
            "matrices_and_vectors": str(
                output_prefix.with_suffix(".npz").resolve()
            ),
        },
    }
    output_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    output_prefix.with_suffix(".md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--excel",
        default=str(
            ROOT
            / "distillation_column_template_20stage_chemsep_warmer_feed_seed_preserved_mv18_20260524.xlsx"
        ),
    )
    parser.add_argument("--dwsim-property-package", default="pr")
    parser.add_argument("--bottoms-light-key-target", type=float, default=0.04717)
    parser.add_argument(
        "--output-prefix",
        default=str(ROOT / "logs" / "reduced_column_feasibility_20260718"),
    )
    return parser.parse_args()


def main() -> int:
    report = run(parse_args())
    print(json.dumps(report, indent=2, allow_nan=True))
    return 0 if report["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
