#!/usr/bin/env python
"""Run the DD-073 five-stage direct steady-state continuation gate."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.direct_steady_state_continuation_v1 import (
    build_continuation_stages,
    solve_direct_steady_state_continuation,
)
from dynamic_distillation.direct_steady_state_registry_v1 import (
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    build_chemsep_guess,
    build_direct_steady_state_problem,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


def _point_doc(point) -> dict:
    return asdict(point)


def _stage_doc(stage_result) -> dict:
    return {
        "stage": stage_result.stage.number,
        "name": stage_result.stage.name,
        "size": stage_result.stage.size,
        "accepted": stage_result.accepted,
        "final_lambda": stage_result.final_lambda,
        "reason": stage_result.reason,
        "uncolored_endpoint_max_difference": (
            stage_result.uncolored_endpoint_max_difference
        ),
        "points": [_point_doc(point) for point in stage_result.points],
    }


def _profile(problem, vector: np.ndarray) -> list[dict]:
    names = {
        entry.name: index for index, entry in enumerate(problem.registry.unknowns)
    }
    nodes = (
        "reflux_drum",
        *(f"tray_{stage}" for stage in problem.registry.active_stage_ids),
        "partial_reboiler",
    )
    rows = []
    for node in nodes:
        row = {
            "node": node,
            "T_F": float(vector[names[f"T[{node}]"]]),
            "P_psia": float(vector[names[f"P[{node}]"]]),
            "NL_lbmol": float(vector[names[f"NL[{node}]"]]),
            "NV_lbmol": float(vector[names[f"NV[{node}]"]]),
        }
        for phase in ("x", "y"):
            independent = [
                float(vector[names[f"{phase}[{node},{component}]"]])
                for component in problem.registry.component_names[:-1]
            ]
            composition = independent + [1.0 - sum(independent)]
            for component, value in zip(problem.registry.component_names, composition):
                row[f"{phase}_{component}"] = float(value)
        liquid_name = f"L_out[{node}]"
        vapor_name = f"V_out[{node}]"
        row["L_out_lbmolph"] = (
            float(vector[names[liquid_name]]) if liquid_name in names else None
        )
        row["V_out_lbmolph"] = (
            float(vector[names[vapor_name]]) if vapor_name in names else None
        )
        rows.append(row)
    return rows


def _comparison(initial: list[dict], final: list[dict]) -> dict:
    numeric_keys = tuple(
        key
        for key, value in initial[0].items()
        if key != "node" and value is not None
    )
    rows = []
    maxima = {key: 0.0 for key in numeric_keys}
    for start, end in zip(initial, final):
        row = {"node": start["node"]}
        for key in numeric_keys:
            if start[key] is None or end[key] is None:
                continue
            delta = float(end[key] - start[key])
            row[f"delta_{key}"] = delta
            maxima[key] = max(maxima[key], abs(delta))
        rows.append(row)
    return {"maximum_absolute_delta": maxima, "rows": rows}


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-073 Direct Steady-State Continuation",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Accepted direct root: `{report['accepted']}`",
        f"- Final completed stage: `{report['final_stage']}/5`",
        f"- Live thermo: `{report['thermo_backend']}`",
        f"- Wall time: `{report['wall_time_sec']:.2f} s`",
        f"- Final scaled infinity norm: "
        f"`{report['final_evaluation']['scaled_inf_norm']:.6g}`",
        "",
        "## Stage Results",
        "",
        "| Stage | System | Size | Accepted | Final lambda | Accepted points | Last condition |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for stage in report["stages"]:
        accepted_points = [point for point in stage["points"] if point["accepted"]]
        last = stage["points"][-1] if stage["points"] else {}
        lines.append(
            f"| {stage['stage']} | {stage['name']} | {stage['size']} | "
            f"{stage['accepted']} | {stage['final_lambda']:.6g} | "
            f"{len(accepted_points)} | "
            f"{last.get('condition_estimate', float('nan')):.6g} |"
        )
    lines.extend(["", "## Final Physical Residuals", ""])
    for block, value in report["final_evaluation"]["block_maxima"].items():
        lines.append(f"- `{block}`: `{value:.6g}`")
    if report["final_gate_failures"]:
        lines.extend(["", "Final gate failures:"])
        lines.extend(f"- {failure}" for failure in report["final_gate_failures"])
    lines.extend(["", "## Dominant Residuals", ""])
    for row in report["final_evaluation"]["dominant_scaled_residuals"]:
        lines.append(
            f"- `{row['name']}`: scaled `{row['scaled_value']:.6g}`, "
            f"raw `{row['raw_value']:.6g} {row['units']}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            report["reason"],
            "",
            "A failed stage localizes the unresolved equation family. A Stage 5 "
            "root is still only a direct steady-state feasibility result; "
            "serialization and dynamic testing require later gates.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
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
    provider = ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=args.dwsim_property_package,
    )
    problem = build_direct_steady_state_problem(
        registry=registry,
        column=column,
        provider=provider,
        bottoms_light_key_target=args.bottoms_light_key_target,
    )
    initial = build_chemsep_guess(problem)
    stages = build_continuation_stages(problem)
    accepted_points = []
    accepted_vectors = []

    def save_accepted(point, vector):
        accepted_points.append(_point_doc(point))
        accepted_vectors.append(np.asarray(vector, dtype=float).copy())

    result = solve_direct_steady_state_continuation(
        problem,
        initial,
        homotopy_tolerance=args.homotopy_tolerance,
        final_physical_tolerance=args.final_physical_tolerance,
        condition_limit=args.condition_limit,
        condition_growth_limit=args.condition_growth_limit,
        max_nfev=args.max_nfev,
        verify_uncolored_endpoints=args.verify_uncolored_endpoints,
        accepted_state_callback=save_accepted,
    )
    initial_profile = _profile(problem, initial)
    final_profile = _profile(problem, result.final_vector)
    block_maxima = dict(result.final_block_maxima)
    report = {
        "classification": result.classification,
        "accepted": result.accepted,
        "reason": result.reason,
        "excel_path": str(Path(args.excel).resolve()),
        "thermo_backend": f"DWSIM {args.dwsim_property_package.upper()}",
        "solver": {
            "method": "scipy.optimize.least_squares(method=trf, tr_solver=lsmr)",
            "jacobian": "transformed-coordinate colored central finite difference",
            "initial_delta_lambda": 0.10,
            "minimum_delta_lambda": 1.0 / 128.0,
            "maximum_step_growth": 1.5,
            "maximum_consecutive_reductions": 6,
            "max_nfev_per_attempt": args.max_nfev,
            "homotopy_tolerance": args.homotopy_tolerance,
            "final_physical_tolerance": args.final_physical_tolerance,
            "condition_limit": args.condition_limit,
            "condition_growth_limit": args.condition_growth_limit,
            "verify_uncolored_endpoints": args.verify_uncolored_endpoints,
        },
        "stage_dimensions": [stage.size for stage in stages],
        "final_stage": result.final_stage,
        "stages": [_stage_doc(stage) for stage in result.stages],
        "accepted_continuation_points": accepted_points,
        "final_evaluation": {
            "scaled_l2_norm": result.final_evaluation.scaled_l2_norm,
            "scaled_inf_norm": result.final_evaluation.scaled_inf_norm,
            "block_maxima": block_maxima,
            "dominant_scaled_residuals": list(
                result.final_evaluation.dominant_scaled_residuals
            ),
            "component_conservation_pass": (
                result.final_evaluation.conservation.component_pass
            ),
            "component_relative_error": (
                result.final_evaluation.conservation.component_relative_error.tolist()
            ),
            "energy_conservation_pass": (
                result.final_evaluation.conservation.energy_pass
            ),
            "energy_relative_error": (
                result.final_evaluation.conservation.energy_relative_error
            ),
            "safeguards_used": list(result.final_evaluation.safeguards_used),
        },
        "final_gate_failures": list(result.final_gate_failures),
        "physical_final_matches_direct_evaluator": (
            result.physical_final_matches_direct_evaluator
        ),
        "chemsep_profile": initial_profile,
        "final_profile": final_profile,
        "chemsep_comparison": _comparison(initial_profile, final_profile),
        "wall_time_sec": float(time.perf_counter() - started),
    }
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report), encoding="utf-8"
    )
    np.savez_compressed(
        out_prefix.with_name(out_prefix.name + "_states").with_suffix(".npz"),
        initial_vector=initial,
        final_vector=result.final_vector,
        accepted_vectors=(
            np.stack(accepted_vectors, axis=0)
            if accepted_vectors
            else np.empty((0, len(initial)), dtype=float)
        ),
        unknown_names=np.asarray(
            [entry.name for entry in registry.unknowns], dtype=object
        ),
        accepted_points_json=np.asarray(
            json.dumps(accepted_points), dtype=object
        ),
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", required=True)
    parser.add_argument("--dwsim-property-package", default="pr")
    parser.add_argument("--bottoms-light-key-target", type=float, default=0.04717)
    parser.add_argument("--homotopy-tolerance", type=float, default=1.0e-7)
    parser.add_argument("--final-physical-tolerance", type=float, default=1.0e-6)
    parser.add_argument("--condition-limit", type=float, default=1.0e12)
    parser.add_argument("--condition-growth-limit", type=float, default=100.0)
    parser.add_argument("--max-nfev", type=int, default=200)
    parser.add_argument(
        "--verify-uncolored-endpoints",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--out-prefix",
        default=r"logs\direct_steady_state_continuation_20260718",
    )
    return parser


if __name__ == "__main__":
    report = run(_parser().parse_args())
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "accepted": report["accepted"],
                "final_stage": report["final_stage"],
                "final_scaled_inf_norm": report["final_evaluation"][
                    "scaled_inf_norm"
                ],
                "wall_time_sec": report["wall_time_sec"],
                "reason": report["reason"],
            },
            indent=2,
        )
    )
