#!/usr/bin/env python
"""Solve the water-methanol stationary equations at a prescribed pressure profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_stationary_root as free_root  # noqa: E402
from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.prescribed_pressure_stationary_v1 import (  # noqa: E402
    apply_prescribed_pressure_targets,
    prescribed_pressure_structural_pattern,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
    stationary_variable_names,
)


DEFAULT_JSON = Path("logs/core_v3_water_methanol_prescribed_pressure_root_20260901.json")
DEFAULT_DOC = Path("docs/core_v3_water_methanol_prescribed_pressure_root_20260901.md")
DEFAULT_EVIDENCE = Path("logs/core_v3_water_methanol_prescribed_pressure_root_20260901.npz")
SETTINGS = {
    "method": "trf",
    "difference_step": 1.0e-5,
    "ftol": 1.0e-11,
    "xtol": 1.0e-11,
    "gtol": 1.0e-11,
    "max_nfev": 120,
}
LIMITS = {
    "scaled_residual_inf_norm": 1.0e-8,
    "component_balance_lbmolph": 1.0e-6,
    "energy_balance_BTUph": 1.0e-3,
    "pressure_target_psia": 1.0e-8,
    "fugacity_residual": 1.0e-8,
    "relative_eos_residual": 1.0e-10,
    "terminal_inventory_lbmol": 1.0e-8,
    "jacobian_condition": 1.0e8,
    "minimum_bound_distance": 1.0e-6,
    "wall_clock_sec": 600.0,
}


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition, singular


def _terminal_levels(endpoint: Any, properties: Any, geometry: Any) -> list[float]:
    liquid_volume = properties.free_volume.liquid_volume_ft3
    capacity = (
        geometry[0].gross_capacity_ft3 - geometry[0].fixed_vapor_extension_ft3,
        geometry[-1].gross_capacity_ft3 - geometry[-1].fixed_vapor_extension_ft3,
    )
    return [float(liquid_volume[0] / capacity[0]), float(liquid_volume[-1] / capacity[1])]


def _profile(problem: dict[str, Any], evaluation: Any) -> list[dict[str, Any]]:
    endpoint = evaluation.base.endpoint
    topology = problem["spec"].topology
    volumes = tuple(topology.volume_ids)
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    liquid_flow = {topology.top_volume: float(problem["spec"].reflux_lbmolph)}
    liquid_flow.update(
        {
            volume: float(endpoint.hydraulic_liquid_flow_lbmolph[index])
            for index, volume in enumerate(topology.hydraulic_volume_ids)
        }
    )
    liquid_flow[topology.bottom_volume] = 0.0
    vapor_flow = {volume: 0.0 for volume in volumes}
    for index, (source, _destination, _symbol) in enumerate(topology.vapor_links):
        vapor_flow[source] = float(endpoint.vapor_flow_lbmolph[index])
    return [
        {
            "stage": index + 1,
            "volume": volume,
            "temperature_F": float(endpoint.temperature_F[index]),
            "pressure_psia": float(endpoint.pressure_psia[index]),
            "liquid_mole_fraction": [float(value) for value in liquid_x[index]],
            "vapor_mole_fraction": [float(value) for value in vapor_y[index]],
            "liquid_flow_lbmolph": liquid_flow[volume],
            "vapor_flow_lbmolph": vapor_flow[volume],
        }
        for index, volume in enumerate(volumes)
    ]


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    problem = starting_state.build_problem(
        density_model="VTPR",
        property_package="unifac",
    )
    contract = problem["contract"]
    dimension = len(contract.variables)
    target_pressure = np.asarray(problem["source"]["pressure_psia"], dtype=float)
    pattern = prescribed_pressure_structural_pattern(contract)
    lower, upper = free_root._bounds(
        contract,
        problem["reference"],
        policy="phase_total",
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    function_calls = 0
    jacobian_calls = 0

    def evaluate(candidate: np.ndarray, label: str) -> Any:
        nonlocal function_calls
        function_calls += 1
        base = evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            candidate,
            state_id=f"water_methanol:prescribed_pressure:{label}:{function_calls}",
            evaluation_kind="residual" if label == "final" else "jacobian",
        )
        return apply_prescribed_pressure_targets(
            contract,
            base,
            target_pressure,
            residual_scale_psia=problem["numerical"].pressure_residual_scale_psia,
        )

    def objective(candidate: np.ndarray, label: str = "solver") -> np.ndarray:
        return evaluate(candidate, label).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal jacobian_calls
        jacobian_calls += 1
        matrix, _groups = colored_central_difference_jacobian(
            lambda point, state_id: objective(point, state_id),
            candidate,
            pattern=pattern,
            step=float(SETTINGS["difference_step"]),
            state_id=f"water_methanol:prescribed_pressure:jacobian:{jacobian_calls}",
        )
        return matrix

    started = time.perf_counter()
    solution = least_squares(
        lambda point: objective(point),
        np.zeros(dimension),
        jac=jacobian,
        bounds=(lower, upper),
        method=str(SETTINGS["method"]),
        x_scale="jac",
        ftol=float(SETTINGS["ftol"]),
        xtol=float(SETTINGS["xtol"]),
        gtol=float(SETTINGS["gtol"]),
        max_nfev=int(SETTINGS["max_nfev"]),
        verbose=0,
    )
    final = evaluate(solution.x, "final")
    endpoint_matrix = jacobian(solution.x)
    rank, condition, singular = _rank_condition(endpoint_matrix)
    wall = float(time.perf_counter() - started)

    base = final.base
    endpoint = base.endpoint
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    component_max = float(
        max(
            np.max(np.abs(base.balances.liquid_component_residual_lbmolph)),
            np.max(np.abs(base.balances.vapor_component_residual_lbmolph)),
        )
    )
    energy_max = float(np.max(np.abs(base.balances.energy_residual_BTUph)))
    pressure_target_max = float(np.max(np.abs(final.pressure_target_residual_psia)))
    fugacity_max = float(np.max(np.abs(base.fugacity_residual)))
    eos_max = float(np.max(np.abs(base.properties.eos_relative_residual)))
    terminal_max = float(np.max(np.abs(base.terminal_inventory_residual_lbmol)))
    residual_max = float(np.max(np.abs(final.scaled)))
    bound_distance = float(np.min(np.minimum(solution.x - lower, upper - solution.x)))
    levels = _terminal_levels(endpoint, base.properties, problem["geometry"])
    workbook_path = problem["workbook"]
    source = problem["source"]
    provider_report = free_root.compact_provider_report(audit.report())
    physical_pass = bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and np.all(base.properties.free_volume.free_vapor_volume_ft3 > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and endpoint.distillate_lbmolph > 0.0
        and endpoint.bottoms_lbmolph > 0.0
    )
    passed = bool(
        solution.success
        and residual_max < LIMITS["scaled_residual_inf_norm"]
        and component_max < LIMITS["component_balance_lbmolph"]
        and energy_max < LIMITS["energy_balance_BTUph"]
        and pressure_target_max < LIMITS["pressure_target_psia"]
        and fugacity_max < LIMITS["fugacity_residual"]
        and eos_max < LIMITS["relative_eos_residual"]
        and terminal_max < LIMITS["terminal_inventory_lbmol"]
        and rank == dimension
        and condition < LIMITS["jacobian_condition"]
        and bound_distance > LIMITS["minimum_bound_distance"]
        and physical_pass
        and provider_report["pass"]
        and not provider_report["fallback_attempted"]
        and wall < LIMITS["wall_clock_sec"]
    )
    product = {
        "distillate": {
            "flow_lbmolph": float(endpoint.distillate_lbmolph),
            "temperature_F": float(endpoint.temperature_F[0]),
            "pressure_psia": float(endpoint.pressure_psia[0]),
            "liquid_mole_fraction": [float(value) for value in liquid_x[0]],
            "molar_enthalpy_BTU_lbmol": float(base.properties.liquid_enthalpy_BTU_lbmol[0]),
            "molar_density_lbmol_ft3": float(base.properties.liquid_density_lbmol_ft3[0]),
        },
        "bottoms": {
            "flow_lbmolph": float(endpoint.bottoms_lbmolph),
            "temperature_F": float(endpoint.temperature_F[-1]),
            "pressure_psia": float(endpoint.pressure_psia[-1]),
            "liquid_mole_fraction": [float(value) for value in liquid_x[-1]],
            "molar_enthalpy_BTU_lbmol": float(base.properties.liquid_enthalpy_BTU_lbmol[-1]),
            "molar_density_lbmol_ft3": float(base.properties.liquid_density_lbmol_ft3[-1]),
        },
    }
    report = {
        "schema_id": "core-v3-water-methanol-prescribed-pressure-root-v1",
        "classification": "stationary_root_accepted" if passed else "stationary_root_rejected",
        "mode": "prescribed_pressure_stationary_parity",
        "workbook": str(workbook_path),
        "workbook_sha256": _sha256(workbook_path),
        "bulk_provider": "dwsim_unifac",
        "liquid_density_provider": "clapeyron_vtpr",
        "pressure_ownership": "workbook_profile_parameter",
        "settings": SETTINGS,
        "limits": LIMITS,
        "solver": {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "function_calls_observed": function_calls,
            "jacobian_calls_observed": jacobian_calls,
            "wall_clock_sec": wall,
        },
        "stationary_equation_score": residual_max,
        "raw_maxima": {
            "component_balance_lbmolph": component_max,
            "energy_balance_BTUph": energy_max,
            "pressure_target_psia": pressure_target_max,
            "free_pressure_equation_mismatch_psia": float(
                np.max(np.abs(base.pressure_drop.residual_psia))
            ),
            "fugacity": fugacity_max,
            "relative_eos": eos_max,
            "terminal_inventory_lbmol": terminal_max,
        },
        "jacobian": {
            "rank": rank,
            "dimension": dimension,
            "condition": condition,
            "singular_values": [float(value) for value in singular],
        },
        "duties": {
            "condenser_BTUph": float(endpoint.condenser_duty_BTUph),
            "reboiler_BTUph": float(problem["spec"].reboiler_duty_BTUph),
        },
        "products": product,
        "terminal_levels": {
            "distillate_drum_fraction": levels[0],
            "bottom_sump_fraction": levels[1],
        },
        "chemsep_comparison": {
            "distillate_flow_difference_lbmolph": float(
                endpoint.distillate_lbmolph - source["distillate_reference_lbmolph"]
            ),
            "bottoms_flow_difference_lbmolph": float(
                endpoint.bottoms_lbmolph - source["bottoms_reference_lbmolph"]
            ),
            "condenser_duty_difference_BTUph": float(
                endpoint.condenser_duty_BTUph - source["condenser_duty_BTUph"]
            ),
            "top_temperature_difference_F": float(
                endpoint.temperature_F[0] - source["temperature_F"][0]
            ),
            "bottom_temperature_difference_F": float(
                endpoint.temperature_F[-1] - source["temperature_F"][-1]
            ),
            "top_liquid_mole_fraction_difference": (
                liquid_x[0] - np.asarray(source["liquid_mole_fraction"])[0]
            ).tolist(),
            "bottom_liquid_mole_fraction_difference": (
                liquid_x[-1] - np.asarray(source["liquid_mole_fraction"])[-1]
            ).tolist(),
        },
        "minimum_bound_distance": bound_distance,
        "physical_pass": physical_pass,
        "provider": provider_report,
        "tray_profiles": _profile(problem, final),
        "pass_gate": passed,
        "decision": (
            "prescribed_pressure_parity_quantified"
            if passed
            else "stop_prescribed_pressure_nonlinear_work"
        ),
    }
    evidence = {
        "coordinates": solution.x,
        "raw_residual": final.raw,
        "scaled_residual": final.scaled,
        "structural_pattern": pattern,
        "endpoint_jacobian": endpoint_matrix,
    }
    return report, evidence


def render_markdown(report: dict[str, Any]) -> str:
    solver = report["solver"]
    duties = report["duties"]
    products = report["products"]
    comparison = report["chemsep_comparison"]
    levels = report["terminal_levels"]
    lines = [
        "# Core V3 water-methanol prescribed-pressure stationary root",
        "",
        f"- Result: `{report['classification']}`",
        f"- Equation score: `{report['stationary_equation_score']:.6e}`",
        f"- Solver evaluations: `{solver['nfev']} function / {solver['njev']} Jacobian`",
        f"- Jacobian rank/condition: `{report['jacobian']['rank']}/{report['jacobian']['dimension']}` / `{report['jacobian']['condition']:.6e}`",
        f"- Wall time: `{solver['wall_clock_sec']:.3f} s`",
        f"- Free-pressure mismatch retained only as a diagnostic: `{report['raw_maxima']['free_pressure_equation_mismatch_psia']:.6f} psia`",
        "",
        "## Final operating summary",
        "",
        f"- Qc: `{duties['condenser_BTUph']:.6f} BTU/h`",
        f"- Qr: `{duties['reboiler_BTUph']:.6f} BTU/h`",
        f"- Distillate: `{products['distillate']['flow_lbmolph']:.6f} lbmol/h`, "
        f"`T={products['distillate']['temperature_F']:.6f} F`, `P={products['distillate']['pressure_psia']:.6f} psia`, "
        f"`x={products['distillate']['liquid_mole_fraction']}`",
        f"- Bottoms: `{products['bottoms']['flow_lbmolph']:.6f} lbmol/h`, "
        f"`T={products['bottoms']['temperature_F']:.6f} F`, `P={products['bottoms']['pressure_psia']:.6f} psia`, "
        f"`x={products['bottoms']['liquid_mole_fraction']}`",
        f"- Distillate drum level: `{100.0 * levels['distillate_drum_fraction']:.6f}%`",
        f"- Bottom sump level: `{100.0 * levels['bottom_sump_fraction']:.6f}%`",
        f"- Stationary equation score: `{report['stationary_equation_score']:.6e}`",
        "",
        "## Difference from ChemSep",
        "",
        f"- D/B flow difference: `{comparison['distillate_flow_difference_lbmolph']:+.6f}` / `{comparison['bottoms_flow_difference_lbmolph']:+.6f} lbmol/h`",
        f"- Qc difference: `{comparison['condenser_duty_difference_BTUph']:+.6f} BTU/h`",
        f"- Top/bottom temperature difference: `{comparison['top_temperature_difference_F']:+.6f}` / `{comparison['bottom_temperature_difference_F']:+.6f} F`",
        "",
        "## Tray profiles",
        "",
        "| Stage | Volume | T (F) | P (psia) | x1 | x2 | y1 | y2 | L (lbmol/h) | V (lbmol/h) |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["tray_profiles"]:
        lines.append(
            f"| {row['stage']} | {row['volume']} | {row['temperature_F']:.6f} | "
            f"{row['pressure_psia']:.6f} | {row['liquid_mole_fraction'][0]:.9f} | "
            f"{row['liquid_mole_fraction'][1]:.9f} | {row['vapor_mole_fraction'][0]:.9f} | "
            f"{row['vapor_mole_fraction'][1]:.9f} | {row['liquid_flow_lbmolph']:.6f} | "
            f"{row['vapor_flow_lbmolph']:.6f} |"
        )
    lines.append("")
    return "\n".join(lines)


def print_summary(report: dict[str, Any]) -> None:
    duties = report["duties"]
    products = report["products"]
    levels = report["terminal_levels"]
    print(f"Qc={duties['condenser_BTUph']:.6f} BTU/h")
    print(f"Qr={duties['reboiler_BTUph']:.6f} BTU/h")
    for name in ("distillate", "bottoms"):
        row = products[name]
        print(
            f"{name}: F={row['flow_lbmolph']:.6f} lbmol/h, "
            f"T={row['temperature_F']:.6f} F, P={row['pressure_psia']:.6f} psia, "
            f"x={row['liquid_mole_fraction']}"
        )
    print(
        f"levels: top={100.0 * levels['distillate_drum_fraction']:.6f}%, "
        f"bottom={100.0 * levels['bottom_sump_fraction']:.6f}%"
    )
    print(f"stationary_equation_score={report['stationary_equation_score']:.6e}")
    print("tray_profiles:")
    for row in report["tray_profiles"]:
        print(
            f"stage={row['stage']:02d} T={row['temperature_F']:.6f} "
            f"P={row['pressure_psia']:.6f} x={row['liquid_mole_fraction']} "
            f"y={row['vapor_mole_fraction']} L={row['liquid_flow_lbmolph']:.6f} "
            f"V={row['vapor_flow_lbmolph']:.6f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    report, evidence = execute()
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    evidence_path = _rooted(args.evidence)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    np.savez_compressed(evidence_path, **evidence)
    print_summary(report)
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
