#!/usr/bin/env python
"""Audit the rejected VTPR endpoint with generic Core V3 closure tools."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_stationary_root as stationary_root  # noqa: E402

from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.stationary_closure_audit_v1 import (  # noqa: E402
    eos_required_vapor_component_inventory,
    find_active_coordinate_bounds,
    stationary_energy_closure,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
)


DEFAULT_SOURCE = Path(
    "logs/core_v3_water_methanol_vtpr_density_stationary_root_20260831.json"
)
DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_endpoint_closure_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_vtpr_endpoint_closure_20260831.md"
)
PROBE_STEPS = (1.0e-4, 1.0e-3, 1.0e-2, 5.0e-2)


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _metrics(evaluation: Any) -> dict[str, float]:
    return {
        "scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
        "least_squares_cost": float(0.5 * np.dot(evaluation.scaled, evaluation.scaled)),
        "energy_residual_inf_norm_BTUph": float(
            np.max(np.abs(evaluation.balances.energy_residual_BTUph))
        ),
        "eos_relative_residual_inf_norm": float(
            np.max(np.abs(evaluation.properties.eos_relative_residual))
        ),
    }


def execute(source: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    source_path = _rooted(source).resolve()
    saved = json.loads(source_path.read_text(encoding="utf-8"))
    if saved.get("classification") != "stationary_root_rejected":
        raise RuntimeError("closure audit requires a rejected stationary endpoint")
    density_model = saved.get("density_model")
    coordinates = np.asarray(saved["endpoint"]["coordinates"], dtype=float)
    problem = starting_state.build_problem(density_model=density_model)
    contract = problem["contract"]
    if coordinates.shape != (len(contract.variables),):
        raise RuntimeError("saved endpoint does not match the current variable ledger")
    lower, upper = stationary_root._bounds(contract)
    active = find_active_coordinate_bounds(
        contract.variables,
        coordinates,
        lower,
        upper,
    )
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    evaluation_count = 0

    def evaluate(point: np.ndarray, label: str) -> Any:
        nonlocal evaluation_count
        evaluation_count += 1
        return evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            point,
            state_id=f"endpoint_closure:{label}:{evaluation_count}",
            evaluation_kind="residual",
        )

    base = evaluate(coordinates, "base")
    base_metrics = _metrics(base)
    if not np.isclose(
        base_metrics["scaled_residual_inf_norm"],
        float(saved["scaled_residual_inf_norm"]),
        rtol=1.0e-10,
        atol=1.0e-12,
    ):
        raise RuntimeError("saved endpoint residual was not reproduced")

    energy_rows = stationary_energy_closure(
        contract.topology.column,
        base.endpoint,
        base.properties,
        problem["balance_inputs"],
    )
    ledger_residual = np.asarray(
        [row.stationary_energy_residual_BTUph for row in energy_rows],
        dtype=float,
    )
    if not np.allclose(
        ledger_residual,
        base.balances.energy_residual_BTUph,
        rtol=0.0,
        atol=1.0e-6,
    ):
        raise RuntimeError("energy closure ledger does not reproduce the residual")

    required_inventory = eos_required_vapor_component_inventory(
        base.endpoint.vapor_component_inventory_lbmol,
        base.properties.free_volume.free_vapor_volume_ft3,
        base.properties.vapor_molar_volume_ft3_lbmol,
    )
    actual_inventory = np.asarray(
        base.endpoint.vapor_component_inventory_lbmol,
        dtype=float,
    )
    inventory_rows = []
    for volume_index, volume_id in enumerate(contract.topology.column.volume_ids):
        components = []
        for component_index, component_name in enumerate(contract.component_names):
            actual = float(actual_inventory[volume_index, component_index])
            required = float(required_inventory[volume_index, component_index])
            components.append(
                {
                    "component": component_name,
                    "actual_lbmol": actual,
                    "eos_required_lbmol": required,
                    "actual_to_required_ratio": actual / required,
                }
            )
        inventory_rows.append(
            {
                "volume_id": volume_id,
                "actual_total_lbmol": float(np.sum(actual_inventory[volume_index])),
                "eos_required_total_lbmol": float(
                    np.sum(required_inventory[volume_index])
                ),
                "components": components,
            }
        )

    probes = []
    best_outward_norm = base_metrics["scaled_residual_inf_norm"]
    best_outward_cost = base_metrics["least_squares_cost"]
    for finding in active:
        direction = 1.0 if finding.side == "upper" else -1.0
        trials = []
        for step in PROBE_STEPS:
            for sense, multiplier in (("outward", direction), ("inward", -direction)):
                trial_point = coordinates.copy()
                trial_point[finding.index] += multiplier * step
                trial = evaluate(trial_point, f"bound_{finding.index}_{sense}_{step:.1e}")
                metrics = _metrics(trial)
                if sense == "outward":
                    best_outward_norm = min(
                        best_outward_norm,
                        metrics["scaled_residual_inf_norm"],
                    )
                    best_outward_cost = min(
                        best_outward_cost,
                        metrics["least_squares_cost"],
                    )
                trials.append({"sense": sense, "step": step, **metrics})
        probes.append({"bound": asdict(finding), "trials": trials})

    energy_values = np.asarray(base.balances.energy_residual_BTUph, dtype=float)
    energy_spread = float(
        (np.max(energy_values) - np.min(energy_values))
        / max(float(np.max(np.abs(energy_values))), 1.0e-30)
    )
    same_energy_sign = bool(
        np.all(energy_values > 0.0) or np.all(energy_values < 0.0)
    )
    material_energy = energy_values[
        np.abs(energy_values) > 1.0e-6 * np.max(np.abs(energy_values))
    ]
    material_energy_same_sign = bool(
        material_energy.size
        and (np.all(material_energy > 0.0) or np.all(material_energy < 0.0))
    )
    material_energy_spread = float(
        (np.max(material_energy) - np.min(material_energy))
        / max(float(np.max(np.abs(material_energy))), 1.0e-30)
    )
    outward_improvement = float(
        base_metrics["least_squares_cost"] - best_outward_cost
    )
    relative_outward_improvement = float(
        outward_improvement / max(base_metrics["least_squares_cost"], 1.0e-30)
    )
    outward_descent = bool(
        active
        and outward_improvement
        > max(1.0e-14, 1.0e-8 * base_metrics["least_squares_cost"])
    )
    bound_materially_limits_descent = bool(
        outward_descent and relative_outward_improvement > 1.0e-3
    )
    provider_report = audit.report()
    passed = bool(
        active
        and provider_report["pass"]
        and not audit.fallback_attempted
        and np.all(np.isfinite(energy_values))
    )
    return {
        "schema_id": "core-v3-stationary-endpoint-closure-audit-v1",
        "classification": (
            "active_bound_materially_limits_local_descent"
            if bound_materially_limits_descent
            else "active_bound_has_only_marginal_local_descent"
            if outward_descent
            else "active_bound_is_not_a_local_descent_limit"
        ),
        "source_root_result": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "component_specific_logic": False,
        "component_count": len(contract.component_names),
        "volume_count": len(contract.topology.column.volume_ids),
        "density_model": density_model,
        "base_metrics": base_metrics,
        "active_coordinate_bounds": [asdict(item) for item in active],
        "bound_probes": probes,
        "best_outward_scaled_residual_inf_norm": best_outward_norm,
        "best_outward_least_squares_cost": best_outward_cost,
        "outward_least_squares_cost_improvement": outward_improvement,
        "relative_outward_least_squares_cost_improvement": (
            relative_outward_improvement
        ),
        "outward_local_descent_detected": outward_descent,
        "bound_materially_limits_local_descent": bound_materially_limits_descent,
        "vapor_inventory_eos_comparison": inventory_rows,
        "energy_closure": {
            "rows": [asdict(row) for row in energy_rows],
            "same_residual_sign_on_all_volumes": same_energy_sign,
            "relative_residual_spread": energy_spread,
            "material_residuals_same_sign": material_energy_same_sign,
            "material_residual_relative_spread": material_energy_spread,
            "global_external_energy_rate_BTUph": float(
                base.transport.external_energy_rate_BTUph
            ),
            "sum_stationary_energy_residual_BTUph": float(np.sum(energy_values)),
            "ledger_reproduction_tolerance_BTUph": 1.0e-6,
        },
        "provider": provider_report,
        "residual_evaluations": evaluation_count,
        "nonlinear_solve_attempted": False,
        "bounds_changed": False,
        "equations_changed": False,
        "timestep_attempted": False,
        "pass_gate": passed,
        "decision": (
            "review_generic_bound_basis_before_any_second_solve"
            if bound_materially_limits_descent
            else "investigate_generic_energy_closure_before_any_second_solve"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    active = report["active_coordinate_bounds"]
    energy = report["energy_closure"]
    active_text = ", ".join(
        f"{item['variable']} ({item['side']})" for item in active
    ) or "none"
    return "\n".join(
        (
            "# Core V3 stationary endpoint closure audit",
            "",
            f"- Finding: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Active coordinate bounds: `{active_text}`",
            f"- Base scaled residual: `{report['base_metrics']['scaled_residual_inf_norm']:.6e}`",
            f"- Best outward probe residual: `{report['best_outward_scaled_residual_inf_norm']:.6e}`",
            f"- Base/best outward least-squares cost: `{report['base_metrics']['least_squares_cost']:.6e} / {report['best_outward_least_squares_cost']:.6e}`",
            f"- Global external energy rate: `{energy['global_external_energy_rate_BTUph']:.6e} BTU/h`",
            f"- Energy residuals have one sign: `{energy['same_residual_sign_on_all_volumes']}`",
            f"- Component-specific logic: `{report['component_specific_logic']}`",
            "- Nonlinear solve, bound change, equation change, or timestep: `False`",
            "",
            "The audit discovers variables, components, volumes, links, and energy terms from the Core V3 ledgers and topology.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = execute(args.source)
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "active_bound_count": len(report["active_coordinate_bounds"]),
                "best_outward_scaled_residual_inf_norm": report[
                    "best_outward_scaled_residual_inf_norm"
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
