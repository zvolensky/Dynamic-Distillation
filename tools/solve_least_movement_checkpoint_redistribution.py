#!/usr/bin/env python
"""Run the DD-068 multi-start least-movement N+U redistribution probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    build_energy_only_targets,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    build_frozen_checkpoint_bridge,
    run_local_closure_audit,
    run_terminal_closure_audit,
)
from dynamic_distillation.least_movement_redistribution_v1 import (
    assess_multistart_results,
    build_energy_only_pressure_profile_start,
    build_movement_scales,
    conservative_random_start,
    normalized_movement_from_absolute_state,
    solve_least_movement_redistribution,
)
from dynamic_distillation.uv_flash_sandbox_v1 import _build_provider


DD067_ENERGY_MOVE_BTU = 747127.1133593691
DD067_MAX_PRESSURE_CHANGE_PSI = 93.65656224226387


def _finite_or_none(value: float) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def _huber_sum(values: np.ndarray, delta: float = 1.0) -> float:
    absolute = np.abs(np.asarray(values, dtype=float))
    return float(
        np.sum(
            np.where(
                absolute <= float(delta),
                0.5 * np.square(absolute),
                float(delta) * (absolute - 0.5 * float(delta)),
            )
        )
    )


def _load_dd067_start(
    *,
    report_path: Path,
    targets,
    scales,
) -> tuple[np.ndarray, np.ndarray]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = {str(row["node_id"]): row for row in report["nodes"]}
    n_values = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in targets
        ]
    )
    u_values = np.asarray(
        [float(rows[node.node_id]["implied_internal_energy_BTU"]) for node in targets],
        dtype=float,
    )
    q = normalized_movement_from_absolute_state(
        targets=targets,
        scales=scales,
        component_inventory_lbmol=n_values,
        internal_energy_BTU=u_values,
    )
    final_pressure = np.asarray(report["final_pressure_psia"], dtype=float)
    return q, final_pressure


def _result_document(result, *, component_names) -> Dict[str, Any]:
    q_all = np.concatenate(
        [
            np.asarray(result.normalized_component_change).reshape((-1,)),
            np.asarray(result.normalized_energy_change).reshape((-1,)),
        ]
    )
    return {
        "classification": result.classification,
        "converged": result.converged,
        "objective": result.objective,
        "component_objective": result.component_objective,
        "energy_objective": result.energy_objective,
        "normalized_L1": float(np.sum(np.abs(q_all))),
        "normalized_Huber_delta1": _huber_sum(q_all),
        "component_conservation_error_lbmol": (
            result.component_conservation_error_lbmol.tolist()
        ),
        "component_conservation_relative_max": (
            result.component_conservation_relative_max
        ),
        "energy_conservation_error_BTU": result.energy_conservation_error_BTU,
        "energy_conservation_relative": result.energy_conservation_relative,
        "minimum_pressure_increment_psi": (
            result.minimum_pressure_increment_psi
        ),
        "maximum_pressure_order_violation_psi": (
            result.maximum_pressure_order_violation_psi
        ),
        "pressure_ordering_pass": result.pressure_ordering_pass,
        "all_local_closures_pass": result.all_local_closures_pass,
        "active_bound_count": result.active_bound_count,
        "first_order_optimality_norm": result.first_order_optimality_norm,
        "constraint_violation_norm": result.constraint_violation_norm,
        "total_uv_solves": result.total_uv_solves,
        "optimizer_termination_reason": result.optimizer_termination_reason,
        "diagnostics": {
            "material_move_L1_lbmol": (
                result.diagnostics.material_move_L1_lbmol
            ),
            "material_move_L1_by_component_lbmol": {
                str(name): float(value)
                for name, value in zip(
                    component_names,
                    result.diagnostics.material_move_L1_by_component_lbmol,
                )
            },
            "energy_move_L1_BTU": result.diagnostics.energy_move_L1_BTU,
            "component_donor_lbmol": {
                str(name): float(value)
                for name, value in zip(
                    component_names,
                    result.diagnostics.component_donor_lbmol,
                )
            },
            "component_receiver_lbmol": {
                str(name): float(value)
                for name, value in zip(
                    component_names,
                    result.diagnostics.component_receiver_lbmol,
                )
            },
            "energy_donor_BTU": result.diagnostics.energy_donor_BTU,
            "energy_receiver_BTU": result.diagnostics.energy_receiver_BTU,
            "component_sign_reversals": {
                str(name): int(value)
                for name, value in zip(
                    component_names,
                    result.diagnostics.component_sign_reversals,
                )
            },
            "energy_sign_reversals": result.diagnostics.energy_sign_reversals,
            "maximum_scaled_component_change": (
                result.diagnostics.maximum_scaled_component_change
            ),
            "maximum_scaled_energy_change": (
                result.diagnostics.maximum_scaled_energy_change
            ),
            "terminal_component_abs_fraction": (
                result.diagnostics.terminal_component_abs_fraction
            ),
            "terminal_energy_abs_fraction": (
                result.diagnostics.terminal_energy_abs_fraction
            ),
            "maximum_pressure_change_psi": (
                result.diagnostics.maximum_pressure_change_psi
            ),
            "pressure_rms_change_psi": (
                result.diagnostics.pressure_rms_change_psi
            ),
        },
        "iterations": [
            {
                "iteration": row.iteration,
                "objective": row.objective,
                "component_objective": row.component_objective,
                "energy_objective": row.energy_objective,
                "maximum_pressure_order_violation_psi": (
                    row.maximum_pressure_order_violation_psi
                ),
                "minimum_pressure_increment_psi": (
                    row.minimum_pressure_increment_psi
                ),
                "step_norm": row.step_norm,
                "accepted_step_fraction": row.accepted_step_fraction,
                "subproblem_success": row.subproblem_success,
                "subproblem_iterations": row.subproblem_iterations,
                "first_order_optimality_norm": (
                    row.first_order_optimality_norm
                ),
                "active_linear_constraint_count": (
                    row.active_linear_constraint_count
                ),
                "uv_solves": row.uv_solves,
                "termination_reason": row.termination_reason,
            }
            for row in result.iterations
        ],
        "nodes": [
            {
                "node_id": row.node_id,
                "position_1based": row.position_1based,
                "component_inventory_lbmol": {
                    str(name): float(value)
                    for name, value in zip(
                        component_names,
                        row.component_inventory_lbmol,
                    )
                },
                "component_change_lbmol": {
                    str(name): float(value)
                    for name, value in zip(
                        component_names,
                        result.component_change_lbmol[idx, :],
                    )
                },
                "internal_energy_BTU": row.internal_energy_BTU,
                "internal_energy_change_BTU": float(
                    result.energy_change_BTU[idx]
                ),
                "T_F": row.closure.T_F,
                "P_psia": row.closure.P_psia,
                "beta_vapor": row.closure.beta_vapor,
                "component_relative_residual": (
                    row.component_relative_residual
                ),
                "energy_relative_residual": row.energy_relative_residual,
                "volume_relative_residual": row.volume_relative_residual,
                "equilibrium_beta_residual": (
                    row.equilibrium_beta_residual
                ),
                "active_bound_count": row.active_bound_count,
            }
            for idx, row in enumerate(result.nodes)
        ],
    }


def _render_markdown(report: Dict[str, Any]) -> str:
    assessment = report["multistart_assessment"]
    best = report.get("best_result")
    lines = [
        "# DD-068 Least-Movement N+U Redistribution",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Hydraulics decision: `{report['hydraulics_decision']}`",
        f"- Thermo: `{report['thermo_mode']}`",
        f"- Checkpoint: `{report['checkpoint_run_id']}` at `{report['checkpoint_time_s']:.6g} s`",
        f"- Primary objective: `{report['primary_objective']}`",
        "",
        "## Multi-Start Evidence",
        "",
        "| Start | Converged | Objective | Energy moved, BTU | Material moved, lbmol | Max dP, psi | Terminal energy fraction |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for start in report["starts"]:
        result = start["result"]
        lines.append(
            f"| {start['name']} | {result['converged']} | "
            f"{result['objective']:.6g} | "
            f"{result['diagnostics']['energy_move_L1_BTU']:.6g} | "
            f"{result['diagnostics']['material_move_L1_lbmol']:.6g} | "
            f"{result['diagnostics']['maximum_pressure_change_psi']:.6g} | "
            f"{result['diagnostics']['terminal_energy_abs_fraction']:.6g} |"
        )
    lines.extend(
        [
            "",
            f"- Successful starts: `{len(assessment['successful_start_names'])}` / `{len(assessment['start_names'])}`",
            f"- Objective relative spread: `{assessment['relative_objective_spread']}`",
            f"- Required spread: `<{assessment['required_relative_spread']}`",
            f"- Reproducible minimum pass: `{assessment['reproducible_minimum_pass']}`",
            f"- Best start: `{assessment['best_start_name']}`",
        ]
    )
    if best is not None:
        diagnostics = best["diagnostics"]
        lines.extend(
            [
                "",
                "## Best Result",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Normalized L2 objective | {best['objective']:.6g} |",
                f"| Component objective | {best['component_objective']:.6g} |",
                f"| Energy objective | {best['energy_objective']:.6g} |",
                f"| Material moved, half L1, lbmol | {diagnostics['material_move_L1_lbmol']:.6g} |",
                f"| Energy moved, half L1, BTU | {diagnostics['energy_move_L1_BTU']:.6g} |",
                f"| DD-067 energy-movement ratio | {report['dd067_comparison']['energy_move_ratio']:.6g} |",
                f"| Maximum pressure change, psi | {diagnostics['maximum_pressure_change_psi']:.6g} |",
                f"| DD-067 max-pressure-change ratio | {report['dd067_comparison']['maximum_pressure_change_ratio']:.6g} |",
                f"| Terminal component correction fraction | {diagnostics['terminal_component_abs_fraction']:.6g} |",
                f"| Terminal energy correction fraction | {diagnostics['terminal_energy_abs_fraction']:.6g} |",
                f"| First-order optimality norm | {best['first_order_optimality_norm']:.6g} |",
                f"| Constraint violation norm | {best['constraint_violation_norm']:.6g} |",
                f"| UV solves | {best['total_uv_solves']} |",
                f"| Active bounds | {best['active_bound_count']} |",
                "",
                "## Best Node Profile",
                "",
                "| Node | T, F | P, psia | Vapor fraction | Delta U, BTU |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in best["nodes"]:
            lines.append(
                f"| {row['node_id']} | {row['T_F']:.6g} | "
                f"{row['P_psia']:.6g} | {row['beta_vapor']:.6g} | "
                f"{row['internal_energy_change_BTU']:.6g} |"
            )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            report["decision"],
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    excel = str(Path(args.excel).resolve())
    checkpoint = str(Path(args.checkpoint).resolve())
    col = build_column_spec_from_case(load_case_from_excel(excel))
    provider, thermo_mode = _build_provider(
        col,
        thermo_mode=args.thermo,
        thermo_table_path=args.thermo_table,
        thermo_pool_workers=None,
        thermo_pool_chunk_size=4,
    )
    try:
        bridge = build_frozen_checkpoint_bridge(
            excel_path=excel,
            checkpoint_path=checkpoint,
            provider=provider,
        )
        local = run_local_closure_audit(bridge=bridge, provider=provider)
        terminal = run_terminal_closure_audit(bridge=bridge, provider=provider)
        targets = build_energy_only_targets(
            bridge=bridge,
            local=local,
            terminal=terminal,
        )
        scales = build_movement_scales(targets)
        requested = tuple(
            item.strip()
            for item in str(args.starts).split(",")
            if item.strip()
        )
        start_vectors: Dict[str, np.ndarray] = {}
        dd067_pressure = None
        if "checkpoint" in requested:
            size = len(targets) * (len(bridge.spec.component_names) + 1)
            start_vectors["checkpoint"] = np.zeros(size, dtype=float)
        needs_dd067 = "dd067" in requested or "linear" in requested
        if needs_dd067:
            dd067_q, dd067_pressure = _load_dd067_start(
                report_path=Path(args.dd067_report),
                targets=targets,
                scales=scales,
            )
            if "dd067" in requested:
                start_vectors["dd067"] = dd067_q
        if "linear" in requested:
            assert dd067_pressure is not None
            linear_pressure = np.linspace(
                float(dd067_pressure[0]),
                float(dd067_pressure[-1]),
                len(targets),
            )
            linear_q, _linear_rows = build_energy_only_pressure_profile_start(
                provider=provider,
                targets=targets,
                base_pressure_psia=linear_pressure,
                scales=scales,
            )
            start_vectors["linear"] = linear_q
        if "random-small" in requested:
            start_vectors["random-small"] = conservative_random_start(
                targets=targets,
                scales=scales,
                relative_magnitude=args.random_small_magnitude,
                seed=args.random_seed,
            )
        if "random-moderate" in requested:
            start_vectors["random-moderate"] = conservative_random_start(
                targets=targets,
                scales=scales,
                relative_magnitude=args.random_moderate_magnitude,
                seed=args.random_seed + 1,
            )
        unknown = sorted(set(requested) - set(start_vectors))
        if unknown:
            raise ValueError(f"unknown or unavailable starts: {unknown}")

        named_results = []
        for name in requested:
            print(f"DD-068 start: {name}", file=sys.stderr, flush=True)
            result = solve_least_movement_redistribution(
                provider=provider,
                targets=targets,
                initial_normalized_movement=start_vectors[name],
                minimum_pressure_increment_psi=args.minimum_pressure_increment,
                maximum_outer_iterations=args.max_outer_iterations,
                sensitivity_relative_step=args.sensitivity_relative_step,
                maximum_scaled_movement=args.maximum_scaled_movement,
            )
            named_results.append((name, result))
            print(
                f"  converged={result.converged} objective={result.objective:.8g} "
                f"violation={result.maximum_pressure_order_violation_psi:.6g}",
                file=sys.stderr,
                flush=True,
            )

        assessment = assess_multistart_results(
            results=named_results,
            required_relative_spread=args.objective_spread_tolerance,
        )
        result_by_name = {name: result for name, result in named_results}
        best = (
            result_by_name.get(str(assessment.best_start_name))
            if assessment.best_start_name is not None
            else None
        )
        component_names = tuple(str(name) for name in bridge.spec.component_names)
        start_docs = [
            {
                "name": name,
                "result": _result_document(
                    result,
                    component_names=component_names,
                ),
            }
            for name, result in named_results
        ]
        best_doc = (
            _result_document(best, component_names=component_names)
            if best is not None
            else None
        )
        if best is None:
            energy_ratio = float("inf")
            pressure_ratio = float("inf")
        else:
            energy_ratio = (
                best.diagnostics.energy_move_L1_BTU
                / DD067_ENERGY_MOVE_BTU
            )
            pressure_ratio = (
                best.diagnostics.maximum_pressure_change_psi
                / DD067_MAX_PRESSURE_CHANGE_PSI
            )
        all_starts_converged = bool(
            len(assessment.successful_start_names)
            == len(assessment.start_names)
        )
        go_hydraulics = bool(
            best is not None
            and all_starts_converged
            and assessment.reproducible_minimum_pass
            and best.converged
            and energy_ratio < 0.5
            and pressure_ratio < 0.5
            and best.diagnostics.terminal_energy_abs_fraction < 0.5
            and best.diagnostics.terminal_component_abs_fraction < 0.5
        )
        hydraulics_decision = (
            "go_to_uncapped_hydraulics"
            if go_hydraulics
            else "stop_before_hydraulics"
        )
        failed_gates = []
        if not all_starts_converged:
            failed_gates.append(
                f"only {len(assessment.successful_start_names)} of "
                f"{len(assessment.start_names)} starts converged"
            )
        if not assessment.reproducible_minimum_pass:
            failed_gates.append("the successful starts did not reproduce one objective")
        if energy_ratio >= 0.5:
            failed_gates.append(
                f"energy movement is {energy_ratio:.3f} times DD-067"
            )
        if pressure_ratio >= 0.5:
            failed_gates.append(
                f"maximum pressure correction is {pressure_ratio:.3f} times DD-067"
            )
        if (
            best is not None
            and best.diagnostics.terminal_energy_abs_fraction >= 0.5
        ):
            failed_gates.append(
                "terminal assemblies absorb "
                f"{best.diagnostics.terminal_energy_abs_fraction:.1%} "
                "of absolute energy movement"
            )
        if (
            best is not None
            and best.diagnostics.terminal_component_abs_fraction >= 0.5
        ):
            failed_gates.append(
                "terminal assemblies absorb "
                f"{best.diagnostics.terminal_component_abs_fraction:.1%} "
                "of absolute component movement"
            )
        if go_hydraulics:
            decision = (
                "The reproducible least-movement result improves both DD-067 movement "
                "metrics by more than a factor of two without terminal domination. "
                "Proceed to a separate uncapped hydraulic closure using this state only "
                "as the algebraic initial guess."
            )
        else:
            decision = (
                "Do not add hydraulics. Failed gates: "
                + "; ".join(failed_gates)
                + ". Audit checkpoint energy allocation, stage and terminal volumes, "
                "vapor-space treatment, and terminal mapping before increasing model "
                "complexity."
            )
        classification = (
            "dd068_go_to_uncapped_hydraulics"
            if go_hydraulics
            else "dd068_stop_before_hydraulics"
        )
        report: Dict[str, Any] = {
            "classification": classification,
            "hydraulics_decision": hydraulics_decision,
            "decision": decision,
            "primary_objective": "normalized_L2_component_plus_energy",
            "diagnostic_objectives": ["L1", "Huber_delta_1"],
            "thermo_mode": thermo_mode,
            "excel_path": bridge.excel_path,
            "checkpoint_path": bridge.checkpoint_path,
            "checkpoint_run_id": bridge.checkpoint_run_id,
            "checkpoint_time_s": bridge.checkpoint_time_s,
            "component_names": list(component_names),
            "starts": start_docs,
            "multistart_assessment": {
                "start_names": list(assessment.start_names),
                "successful_start_names": list(
                    assessment.successful_start_names
                ),
                "objective_values": assessment.objective_values.tolist(),
                "minimum_objective": _finite_or_none(
                    assessment.minimum_objective
                ),
                "maximum_objective": _finite_or_none(
                    assessment.maximum_objective
                ),
                "relative_objective_spread": _finite_or_none(
                    assessment.relative_objective_spread
                ),
                "required_relative_spread": (
                    assessment.required_relative_spread
                ),
                "reproducible_minimum_pass": (
                    assessment.reproducible_minimum_pass
                ),
                "best_start_name": assessment.best_start_name,
            },
            "best_result": best_doc,
            "dd067_comparison": {
                "energy_move_L1_BTU": DD067_ENERGY_MOVE_BTU,
                "maximum_pressure_change_psi": (
                    DD067_MAX_PRESSURE_CHANGE_PSI
                ),
                "energy_move_ratio": _finite_or_none(energy_ratio),
                "maximum_pressure_change_ratio": _finite_or_none(
                    pressure_ratio
                ),
            },
            "go_gate": {
                "all_starts_converged_required": True,
                "all_starts_converged": all_starts_converged,
                "reproducible_minimum_required": True,
                "energy_move_ratio_max": 0.5,
                "maximum_pressure_change_ratio_max": 0.5,
                "terminal_energy_abs_fraction_max": 0.5,
                "terminal_component_abs_fraction_max": 0.5,
                "pass": go_hydraulics,
            },
        }
        out_prefix = Path(args.out_prefix)
        out_prefix.parent.mkdir(parents=True, exist_ok=True)
        json_path = out_prefix.with_suffix(".json")
        md_path = out_prefix.with_suffix(".md")
        json_path.write_text(
            json.dumps(report, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        md_path.write_text(_render_markdown(report), encoding="utf-8")
        report["json_path"] = str(json_path.resolve())
        report["markdown_path"] = str(md_path.resolve())
        return report
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument(
        "--thermo",
        choices=["dwsim", "table", "table-pool", "auto"],
        default="dwsim",
    )
    parser.add_argument("--thermo-table", default=r"cache\thermo_table.json")
    parser.add_argument(
        "--dd067-report",
        default=r"logs\conservative_checkpoint_redistribution_20260717.json",
    )
    parser.add_argument(
        "--starts",
        default="checkpoint,dd067,linear,random-small,random-moderate",
    )
    parser.add_argument("--minimum-pressure-increment", type=float, default=0.01)
    parser.add_argument("--max-outer-iterations", type=int, default=8)
    parser.add_argument("--sensitivity-relative-step", type=float, default=1.0e-4)
    parser.add_argument("--maximum-scaled-movement", type=float, default=10.0)
    parser.add_argument("--random-small-magnitude", type=float, default=0.01)
    parser.add_argument("--random-moderate-magnitude", type=float, default=0.05)
    parser.add_argument("--random-seed", type=int, default=68068)
    parser.add_argument("--objective-spread-tolerance", type=float, default=1.0e-4)
    parser.add_argument(
        "--out-prefix",
        default=r"logs\least_movement_checkpoint_redistribution_20260717",
    )
    return parser


if __name__ == "__main__":
    print(json.dumps(run(_parser().parse_args()), indent=2))
