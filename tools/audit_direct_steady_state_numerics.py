#!/usr/bin/env python
"""Run the DD-072 residual, conservation, scaling, and Jacobian gate."""

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
from dynamic_distillation.direct_steady_state_registry_v1 import (
    audit_registry_structure,
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
    structural_pattern,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    DirectResidualEvaluationError,
    audit_numerical_jacobian,
    build_bounded_perturbed_guess,
    build_checkpoint_guess_from_diagnostics,
    build_chemsep_guess,
    build_direct_steady_state_problem,
    evaluate_direct_steady_state_residual,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


def _evaluation_doc(evaluation, registry) -> dict:
    rows = [asdict(row) for row in evaluation.rows]
    block_scales: dict[str, list[float]] = {}
    for row in rows:
        key = f"{row['block']} [{row['units']}]"
        block_scales.setdefault(key, []).append(float(row["scale"]))
    variable_scales: dict[str, list[float]] = {}
    for entry, scale in zip(registry.unknowns, evaluation.variable_scales):
        key = f"{entry.block} [{entry.units}]"
        variable_scales.setdefault(key, []).append(float(scale))
    return {
        "valid": True,
        "residual_count": len(rows),
        "all_finite": bool(
            np.all(np.isfinite(evaluation.raw))
            and np.all(np.isfinite(evaluation.scaled))
        ),
        "raw_l2_norm": evaluation.raw_l2_norm,
        "scaled_l2_norm": evaluation.scaled_l2_norm,
        "scaled_inf_norm": evaluation.scaled_inf_norm,
        "dominant_scaled_residuals": list(
            evaluation.dominant_scaled_residuals
        ),
        "safeguards_used": list(evaluation.safeguards_used),
        "variable_scaling": {
            "minimum": float(np.min(evaluation.variable_scales)),
            "maximum": float(np.max(evaluation.variable_scales)),
            "maximum_to_minimum_ratio": float(
                np.max(evaluation.variable_scales)
                / np.min(evaluation.variable_scales)
            ),
            "by_block_and_units": {
                block: {
                    "minimum": min(values),
                    "maximum": max(values),
                    "ratio": max(values) / min(values),
                }
                for block, values in variable_scales.items()
            },
        },
        "residual_scaling": {
            "minimum": float(np.min(evaluation.residual_scales)),
            "maximum": float(np.max(evaluation.residual_scales)),
            "maximum_to_minimum_ratio": float(
                np.max(evaluation.residual_scales)
                / np.min(evaluation.residual_scales)
            ),
            "by_block_and_units": {
                block: {
                    "minimum": min(values),
                    "maximum": max(values),
                    "ratio": max(values) / min(values),
                }
                for block, values in block_scales.items()
            },
        },
        "conservation": {
            "component_lhs_lbmolph": (
                evaluation.conservation.component_lhs_lbmolph.tolist()
            ),
            "component_rhs_lbmolph": (
                evaluation.conservation.component_rhs_lbmolph.tolist()
            ),
            "component_relative_error": (
                evaluation.conservation.component_relative_error.tolist()
            ),
            "component_pass": evaluation.conservation.component_pass,
            "energy_lhs_BTUph": evaluation.conservation.energy_lhs_BTUph,
            "energy_rhs_BTUph": evaluation.conservation.energy_rhs_BTUph,
            "energy_relative_error": (
                evaluation.conservation.energy_relative_error
            ),
            "energy_pass": evaluation.conservation.energy_pass,
            "internal_energy_pairing_pass": (
                evaluation.conservation.internal_energy_pairing_pass
            ),
            "internal_energy_terms": list(
                evaluation.conservation.internal_energy_terms
            ),
        },
        "residuals": rows,
    }


def _jacobian_doc(audit) -> dict:
    return {
        key: value
        for key, value in asdict(audit).items()
        if key != "matrix"
    }


def _failed_evaluation(exc: Exception) -> dict:
    result = {
        "valid": False,
        "error_type": type(exc).__name__,
        "reason": str(exc),
    }
    if isinstance(exc, DirectResidualEvaluationError):
        result.update({"node": exc.node, "phase": exc.phase})
    return result


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-072 Numerical Residual And Jacobian Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Gate passed: `{report['pass_gate']}`",
        f"- Nonlinear solve attempted: `{report['nonlinear_solve_attempted']}`",
        f"- Live thermo: `{report['thermo_backend']}`",
        f"- Wall time: `{report['wall_time_sec']:.2f} s`",
        "",
        "## Guess Results",
        "",
        "| Guess | Valid | Scaled L2 | Component telescope | Energy telescope | Rank h | Rank h/2 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, guess in report["guesses"].items():
        evaluation = guess["evaluation"]
        jacobians = guess.get("jacobians", {})
        lines.append(
            "| {name} | {valid} | {norm} | {component} | {energy} | {rank_h} | {rank_h2} |".format(
                name=name,
                valid=evaluation.get("valid", False),
                norm=(
                    f"{evaluation['scaled_l2_norm']:.6g}"
                    if evaluation.get("valid")
                    else "-"
                ),
                component=(
                    evaluation.get("conservation", {}).get(
                        "component_pass", False
                    )
                ),
                energy=(
                    evaluation.get("conservation", {}).get(
                        "energy_pass", False
                    )
                ),
                rank_h=jacobians.get("h", {}).get("rank", "-"),
                rank_h2=jacobians.get("h_over_2", {}).get("rank", "-"),
            )
        )
    lines.extend(
        [
            "",
            "## Reference Pattern Check",
            "",
            f"- Uncolored rank: `{report['uncolored_reference']['rank']}`",
            f"- Unexpected numerical nonzeros: `{len(report['uncolored_reference']['unexpected_nonzeros'])}`",
            f"- Structurally allowed entries numerically zero: `{len(report['uncolored_reference']['expected_but_zero'])}`",
            f"- Colored/uncolored maximum expected-entry difference: "
            f"`{report['colored_uncolored_max_expected_difference']:.6g}`",
            "",
            "The structurally allowed pattern is intentionally an upper bound. "
            "Numerically zero allowed entries are reported, while any nonzero "
            "outside the registered graph fails the gate.",
            "",
            "## Dominant Residuals",
            "",
        ]
    )
    for name, guess in report["guesses"].items():
        lines.extend([f"### {name}", ""])
        evaluation = guess["evaluation"]
        if not evaluation.get("valid"):
            lines.append(f"- Evaluation failed: `{evaluation['reason']}`")
        else:
            for row in evaluation["dominant_scaled_residuals"][:8]:
                lines.append(
                    f"- `{row['name']}`: scaled `{row['scaled_value']:.6g}`, "
                    f"raw `{row['raw_value']:.6g} {row['units']}`"
                )
        lines.append("")
    lines.extend(
        [
            "## Decision",
            "",
            report["decision"],
            "",
            "DD-072 performs no Newton step, least-squares step, line search, "
            "continuation, optimization, or state correction.",
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
    structure = audit_registry_structure(registry)
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
    chemsep = build_chemsep_guess(problem)
    guesses: dict[str, np.ndarray] = {
        "chemsep": chemsep,
        "perturbed_chemsep": build_bounded_perturbed_guess(problem, chemsep),
    }
    checkpoint_mapping_error = None
    if args.checkpoint:
        try:
            with np.load(args.checkpoint, allow_pickle=True) as checkpoint:
                guesses["checkpoint"] = build_checkpoint_guess_from_diagnostics(
                    problem, chemsep, checkpoint
                )
        except Exception as exc:
            checkpoint_mapping_error = _failed_evaluation(exc)

    guess_docs: dict[str, dict] = {}
    matrices: dict[str, np.ndarray] = {}
    audits: dict[str, tuple[Any, Any]] = {}
    for name, vector in guesses.items():
        try:
            evaluation = evaluate_direct_steady_state_residual(problem, vector)
            jac_h = audit_numerical_jacobian(
                problem, vector, step_factor=1.0, mode="colored"
            )
            jac_h2 = audit_numerical_jacobian(
                problem, vector, step_factor=0.5, mode="colored"
            )
            audits[name] = (jac_h, jac_h2)
            matrices[f"{name}__h"] = jac_h.matrix
            matrices[f"{name}__h_over_2"] = jac_h2.matrix
            guess_docs[name] = {
                "evaluation": _evaluation_doc(evaluation, registry),
                "jacobians": {
                    "h": _jacobian_doc(jac_h),
                    "h_over_2": _jacobian_doc(jac_h2),
                    "rank_stable": jac_h.rank == jac_h2.rank,
                },
            }
        except Exception as exc:
            guess_docs[name] = {"evaluation": _failed_evaluation(exc)}
    if checkpoint_mapping_error is not None:
        guess_docs["checkpoint"] = {"evaluation": checkpoint_mapping_error}

    uncolored = audit_numerical_jacobian(
        problem, chemsep, step_factor=1.0, mode="uncolored"
    )
    matrices["chemsep__h_uncolored"] = uncolored.matrix
    colored_chemsep = audits["chemsep"][0]
    expected = structural_pattern(registry).toarray().astype(bool)
    colored_uncolored_difference = float(
        np.max(
            np.abs(
                colored_chemsep.matrix[expected]
                - uncolored.matrix[expected]
            )
        )
    )

    required_names = ("chemsep", "perturbed_chemsep")
    required_valid = all(
        guess_docs[name]["evaluation"].get("valid", False)
        for name in required_names
    )
    required_conservation = all(
        guess_docs[name]["evaluation"]["conservation"]["component_pass"]
        and guess_docs[name]["evaluation"]["conservation"]["energy_pass"]
        and guess_docs[name]["evaluation"]["conservation"][
            "internal_energy_pairing_pass"
        ]
        for name in required_names
        if guess_docs[name]["evaluation"].get("valid", False)
    )
    required_rank = all(
        guess_docs[name]["jacobians"]["h"]["rank"] == len(registry.unknowns)
        and guess_docs[name]["jacobians"]["h_over_2"]["rank"]
        == len(registry.unknowns)
        and guess_docs[name]["jacobians"]["rank_stable"]
        and not guess_docs[name]["jacobians"]["h"]["near_zero_columns"]
        and not guess_docs[name]["jacobians"]["h_over_2"][
            "near_zero_columns"
        ]
        for name in required_names
        if guess_docs[name]["evaluation"].get("valid", False)
    )
    no_safeguards = all(
        not guess_docs[name]["evaluation"]["safeguards_used"]
        for name in required_names
        if guess_docs[name]["evaluation"].get("valid", False)
    )
    pattern_pass = bool(
        not uncolored.unexpected_nonzeros
        and colored_uncolored_difference <= 1.0e-12
    )
    pass_gate = bool(
        structure.pass_gate
        and required_valid
        and required_conservation
        and required_rank
        and no_safeguards
        and pattern_pass
    )
    classification = (
        "dd072_numerical_audit_passed"
        if pass_gate
        else "dd072_stopped_before_nonlinear_solve"
    )
    decision = (
        "DD-072 passes the numerical gate. The direct residual is finite at "
        "both ChemSep-related guesses, conservation telescopes, and both "
        "scaled Jacobians are full rank at both step sizes. This authorizes "
        "planning DD-073 bounded continuation, but DD-072 itself does not "
        "attempt a nonlinear solve."
        if pass_gate
        else "DD-072 fails at least one numerical gate. Diagnose the reported "
        "equation, scaling, property, or rank defect before any nonlinear solve."
    )
    report = {
        "classification": classification,
        "pass_gate": pass_gate,
        "decision": decision,
        "excel_path": str(Path(args.excel).resolve()),
        "checkpoint_path": (
            None
            if not args.checkpoint
            else str(Path(args.checkpoint).resolve())
        ),
        "thermo_backend": f"DWSIM {args.dwsim_property_package.upper()}",
        "registry": {
            "unknown_count": len(registry.unknowns),
            "residual_count": len(registry.residuals),
            "structural_rank": structure.structural_rank,
            "structural_nullity": structure.structural_nullity,
        },
        "guesses": guess_docs,
        "uncolored_reference": _jacobian_doc(uncolored),
        "colored_uncolored_max_expected_difference": (
            colored_uncolored_difference
        ),
        "wall_time_sec": float(time.perf_counter() - started),
        "nonlinear_solve_attempted": False,
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
        out_prefix.with_name(out_prefix.name + "_jacobians").with_suffix(".npz"),
        **matrices,
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--dwsim-property-package", default="pr")
    parser.add_argument("--bottoms-light-key-target", type=float, default=0.04717)
    parser.add_argument(
        "--out-prefix",
        default=r"logs\direct_steady_state_numerics_20260718",
    )
    return parser


if __name__ == "__main__":
    result = run(_parser().parse_args())
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "pass_gate": result["pass_gate"],
                "wall_time_sec": result["wall_time_sec"],
                "nonlinear_solve_attempted": result[
                    "nonlinear_solve_attempted"
                ],
            },
            indent=2,
        )
    )
