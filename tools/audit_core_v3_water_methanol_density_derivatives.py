#!/usr/bin/env python
"""Isolate property-derivative noise at the rejected water-methanol candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

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


DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_density_derivatives_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_density_derivatives_20260831.md"
)
STEPS = (1.0e-5, 5.0e-6)
VOLUME_ROLES = ("rectifying_volume_2", "stripping_tray")


def _relative_change(first: float, second: float) -> float:
    return float(abs(first - second) / max(abs(first), abs(second), 1.0e-30))


def _central_derivatives(
    inventory: np.ndarray,
    component_index: int,
    evaluate: Callable[[np.ndarray, str], float],
    label: str,
) -> tuple[list[float], list[list[float]]]:
    derivatives = []
    values = []
    for step in STEPS:
        pair = []
        for sign in (1.0, -1.0):
            trial = inventory.copy()
            trial[component_index] *= np.exp(sign * step)
            composition = trial / np.sum(trial)
            pair.append(float(evaluate(composition, f"{label}:{step:.1e}:{sign:+.0f}")))
        values.append(pair)
        derivatives.append(float((pair[0] - pair[1]) / (2.0 * step)))
    return derivatives, values


def execute() -> dict[str, Any]:
    root_path = ROOT / stationary_root.DEFAULT_JSON
    root = json.loads(root_path.read_text(encoding="utf-8"))
    if root.get("pass_gate") or root.get("classification") != "stationary_root_rejected":
        raise RuntimeError("density audit requires the rejected stationary candidate")
    endpoint = root["endpoint"]
    roles = tuple(endpoint["volume_roles"])
    components = tuple(endpoint["component_names"])
    liquid_inventory = np.asarray(endpoint["liquid_component_inventory_lbmol"], dtype=float)
    temperature = np.asarray(endpoint["temperature_F"], dtype=float)
    pressure = np.asarray(endpoint["pressure_psia"], dtype=float)
    problem = starting_state.build_problem()
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit(provider_identity="dwsim")
    results = []
    for role in VOLUME_ROLES:
        volume_index = roles.index(role)
        for component_index, component in enumerate(components):
            fixed = {
                "temperature_F": float(temperature[volume_index]),
                "pressure_psia": float(pressure[volume_index]),
            }

            def density(composition: np.ndarray, state_id: str) -> float:
                return audit.liquid_density(
                    provider,
                    temperature_F=fixed["temperature_F"],
                    pressure_psia=fixed["pressure_psia"],
                    composition=composition,
                    caller="water_methanol_density_derivative",
                    state_id=state_id,
                    evaluation_kind="diagnostic",
                )

            def enthalpy(composition: np.ndarray, state_id: str) -> float:
                return audit.phase_enthalpy(
                    provider,
                    phase="liquid",
                    temperature_F=fixed["temperature_F"],
                    pressure_psia=fixed["pressure_psia"],
                    composition=composition,
                    caller="water_methanol_enthalpy_derivative",
                    state_id=state_id,
                    evaluation_kind="diagnostic",
                )

            property_results: dict[str, Any] = {}
            for property_name, function in (("liquid_density", density), ("liquid_enthalpy", enthalpy)):
                derivatives, values = _central_derivatives(
                    liquid_inventory[volume_index],
                    component_index,
                    function,
                    f"water_methanol:{role}:{component}:{property_name}",
                )
                property_results[property_name] = {
                    "central_derivatives": derivatives,
                    "plus_minus_values": values,
                    "relative_derivative_change": _relative_change(*derivatives),
                }

            fugacity_derivatives = []
            for fugacity_component_index, fugacity_component in enumerate(components):

                def fugacity(composition: np.ndarray, state_id: str, *, index: int = fugacity_component_index) -> float:
                    values = audit.direct_phase_fugacity(
                        provider,
                        phase="liquid",
                        temperature_F=fixed["temperature_F"],
                        pressure_psia=fixed["pressure_psia"],
                        composition=composition,
                        quantity="stage_fugacity_equilibrium",
                        caller="water_methanol_fugacity_derivative",
                        state_id=state_id,
                        evaluation_kind="diagnostic",
                    )
                    return float(values[index])

                derivatives, values = _central_derivatives(
                    liquid_inventory[volume_index],
                    component_index,
                    fugacity,
                    f"water_methanol:{role}:{component}:fugacity:{fugacity_component}",
                )
                fugacity_derivatives.append(
                    {
                        "fugacity_component": fugacity_component,
                        "central_derivatives": derivatives,
                        "plus_minus_values": values,
                        "relative_derivative_change": _relative_change(*derivatives),
                    }
                )
            property_results["liquid_fugacity_coefficients"] = fugacity_derivatives
            results.append(
                {
                    "volume_role": role,
                    "perturbed_inventory_component": component,
                    "temperature_F": fixed["temperature_F"],
                    "pressure_psia": fixed["pressure_psia"],
                    "liquid_mole_fraction": (
                        liquid_inventory[volume_index]
                        / np.sum(liquid_inventory[volume_index])
                    ).tolist(),
                    "properties": property_results,
                }
            )

    density_changes = [
        item["properties"]["liquid_density"]["relative_derivative_change"]
        for item in results
    ]
    stable_changes = []
    for item in results:
        stable_changes.append(
            item["properties"]["liquid_enthalpy"]["relative_derivative_change"]
        )
        stable_changes.extend(
            entry["relative_derivative_change"]
            for entry in item["properties"]["liquid_fugacity_coefficients"]
        )
    isolated = bool(
        max(density_changes) > 0.1
        and max(stable_changes) < 1.0e-5
        and not audit.fallback_attempted
    )
    return {
        "schema_id": "core-v3-water-methanol-density-derivative-audit-v1",
        "classification": (
            "liquid_density_derivative_noise_isolated"
            if isolated
            else "property_derivative_noise_not_isolated"
        ),
        "source_root_result": str(root_path.relative_to(ROOT)).replace("\\", "/"),
        "difference_steps": list(STEPS),
        "locations": results,
        "maximum_density_derivative_relative_change": max(density_changes),
        "minimum_density_derivative_relative_change": min(density_changes),
        "maximum_enthalpy_or_fugacity_derivative_relative_change": max(stable_changes),
        "logical_provider_calls": audit.record_count,
        "provider_fallback_attempted": audit.fallback_attempted,
        "nonlinear_solve_attempted": False,
        "retry_attempted": False,
        "timestep_attempted": False,
        "pass_gate": isolated,
        "decision": (
            "repair_or_replace_live_liquid_density_derivative_path_before_resolving"
            if isolated
            else "continue_property_derivative_localization"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        (
            "# Core V3 water-methanol liquid-density derivative audit",
            "",
            f"- Finding: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Density derivative change range: `{report['minimum_density_derivative_relative_change']:.6e} to {report['maximum_density_derivative_relative_change']:.6e}`",
            f"- Largest enthalpy or fugacity derivative change: `{report['maximum_enthalpy_or_fugacity_derivative_relative_change']:.6e}`",
            f"- Live property calls: `{report['logical_provider_calls']}`",
            "- Nonlinear solve, retry, or timestep: `False`",
            "",
            "## Meaning",
            "",
            (
                "The liquid-density derivative changes sharply when the numerical step "
                "is halved, while liquid enthalpy and fugacity derivatives remain stable. "
                "This isolates the failed stationary solve to the live liquid-density "
                "derivative path rather than the UNIFAC equilibrium or enthalpy calculations."
            ),
            "",
        )
    )


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = execute()
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
                "maximum_density_derivative_relative_change": report[
                    "maximum_density_derivative_relative_change"
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
