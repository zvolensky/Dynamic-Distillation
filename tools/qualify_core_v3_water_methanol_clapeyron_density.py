#!/usr/bin/env python
"""Qualify Clapeyron liquid-density models for the water-methanol Core V3 case."""

from __future__ import annotations

import argparse
import importlib
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

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_stationary_root as rejected_root  # noqa: E402

from dynamic_distillation.thermo_clapeyron_provider_v1 import (  # noqa: E402
    ThermoClapeyronProviderV1,
)


DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_clapeyron_density_qualification_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_clapeyron_density_qualification_20260831.md"
)
MODELS = ("VTPR", "CPA", "PCSAFT")
DERIVATIVE_STEPS = (1.0e-5, 5.0e-6)
VALUE_PARITY_LIMIT = 0.10
DERIVATIVE_CHANGE_LIMIT = 1.0e-5
REPEATABILITY_LIMIT = 1.0e-12


def _relative_change(first: float, second: float) -> float:
    return float(abs(first - second) / max(abs(first), abs(second), 1.0e-30))


def _association_kwargs(model_name: str) -> tuple[dict[str, Any], str]:
    if model_name not in {"CPA", "PCSAFT"}:
        return {}, "not_applicable"
    module = importlib.import_module("pyclapeyron")
    options = module.AssocOptions(combining=module.jl.Symbol("esd"))
    return {"assoc_options": options}, "esd_combining_rule"


def _profiles() -> tuple[list[dict[str, Any]], Any]:
    starting = starting_state.build_problem()
    reference = starting["reference"]
    roles = tuple(starting["contract"].topology.column.volume_ids)
    liquid_inventory = np.asarray(reference.liquid_component_inventory_lbmol, dtype=float)
    dwsim = starting["provider"]
    profiles = []
    for index, role in enumerate(roles):
        composition = liquid_inventory[index] / np.sum(liquid_inventory[index])
        profiles.append(
            {
                "profile": "workbook_start",
                "role": role,
                "temperature_F": float(reference.temperature_F[index]),
                "pressure_psia": float(reference.pressure_psia[index]),
                "liquid_inventory_lbmol": liquid_inventory[index],
                "liquid_mole_fraction": composition,
            }
        )

    root = json.loads(
        (ROOT / rejected_root.DEFAULT_JSON).read_text(encoding="utf-8")
    )
    endpoint = root["endpoint"]
    rejected_inventory = np.asarray(
        endpoint["liquid_component_inventory_lbmol"], dtype=float
    )
    for index, role in enumerate(endpoint["volume_roles"]):
        composition = rejected_inventory[index] / np.sum(rejected_inventory[index])
        profiles.append(
            {
                "profile": "rejected_candidate",
                "role": role,
                "temperature_F": float(endpoint["temperature_F"][index]),
                "pressure_psia": float(endpoint["pressure_psia"][index]),
                "liquid_inventory_lbmol": rejected_inventory[index],
                "liquid_mole_fraction": composition,
            }
        )
    return profiles, dwsim


def _derivative(
    provider: Any,
    state: dict[str, Any],
    component_index: int,
    step: float,
) -> float:
    values = []
    inventory = np.asarray(state["liquid_inventory_lbmol"], dtype=float)
    for sign in (1.0, -1.0):
        trial = inventory.copy()
        trial[component_index] *= np.exp(sign * step)
        composition = trial / np.sum(trial)
        values.append(
            float(
                provider.liquid_density_lbmol_ft3(
                    state["temperature_F"],
                    state["pressure_psia"],
                    composition,
                )
            )
        )
    return float((values[0] - values[1]) / (2.0 * step))


def _evaluate_model(
    model_name: str,
    profiles: list[dict[str, Any]],
    dwsim: Any,
    component_names: tuple[str, ...],
) -> dict[str, Any]:
    kwargs, association = _association_kwargs(model_name)
    started = time.perf_counter()
    provider = ThermoClapeyronProviderV1(
        component_names,
        component_names,
        model_name=model_name,
        model_kwargs=kwargs,
    )
    provider.validate_backend_available()
    build_seconds = time.perf_counter() - started
    states = []
    density_relative_deltas = []
    derivative_changes = []
    repeatability_deltas = []
    for state in profiles:
        composition = np.asarray(state["liquid_mole_fraction"], dtype=float)
        density = float(
            provider.liquid_density_lbmol_ft3(
                state["temperature_F"], state["pressure_psia"], composition
            )
        )
        dwsim_density = float(
            dwsim.liquid_density_lbmol_ft3(
                state["temperature_F"], state["pressure_psia"], composition
            )
        )
        repeat = float(
            provider.liquid_density_lbmol_ft3(
                state["temperature_F"], state["pressure_psia"], composition
            )
        )
        relative_delta = float((density - dwsim_density) / dwsim_density)
        repeatability = float(abs(repeat - density))
        component_derivatives = []
        for component_index, component in enumerate(component_names):
            derivatives = [
                _derivative(provider, state, component_index, step)
                for step in DERIVATIVE_STEPS
            ]
            change = _relative_change(*derivatives)
            derivative_changes.append(change)
            component_derivatives.append(
                {
                    "component": component,
                    "derivatives": derivatives,
                    "relative_change": change,
                }
            )
        density_relative_deltas.append(relative_delta)
        repeatability_deltas.append(repeatability)
        states.append(
            {
                "profile": state["profile"],
                "role": state["role"],
                "temperature_F": state["temperature_F"],
                "pressure_psia": state["pressure_psia"],
                "liquid_mole_fraction": composition.tolist(),
                "dwsim_density_lbmol_ft3": dwsim_density,
                "clapeyron_density_lbmol_ft3": density,
                "relative_density_delta": relative_delta,
                "repeatability_absolute_delta": repeatability,
                "component_derivatives": component_derivatives,
            }
        )
    max_value_delta = float(np.max(np.abs(density_relative_deltas)))
    median_value_delta = float(np.median(np.abs(density_relative_deltas)))
    max_derivative_change = float(np.max(derivative_changes))
    max_repeatability = float(np.max(repeatability_deltas))
    passed = bool(
        np.all(np.isfinite([item["clapeyron_density_lbmol_ft3"] for item in states]))
        and all(item["clapeyron_density_lbmol_ft3"] > 0.0 for item in states)
        and max_value_delta <= VALUE_PARITY_LIMIT
        and max_derivative_change <= DERIVATIVE_CHANGE_LIMIT
        and max_repeatability <= REPEATABILITY_LIMIT
    )
    return {
        "model": model_name,
        "association_configuration": association,
        "build_seconds": float(build_seconds),
        "state_count": len(states),
        "maximum_absolute_relative_density_delta": max_value_delta,
        "median_absolute_relative_density_delta": median_value_delta,
        "maximum_derivative_relative_change": max_derivative_change,
        "maximum_repeatability_absolute_delta": max_repeatability,
        "states": states,
        "pass_gate": passed,
    }


def execute() -> dict[str, Any]:
    profiles, dwsim = _profiles()
    component_names = ("Water", "Methanol")
    results = [
        _evaluate_model(model, profiles, dwsim, component_names) for model in MODELS
    ]
    passing = [result for result in results if result["pass_gate"]]
    passing.sort(
        key=lambda result: (
            result["maximum_absolute_relative_density_delta"],
            result["median_absolute_relative_density_delta"],
            result["maximum_derivative_relative_change"],
        )
    )
    selected = passing[0]["model"] if passing else None
    passed = bool(selected is not None)
    return {
        "schema_id": "core-v3-water-methanol-clapeyron-density-qualification-v1",
        "profiles": ["workbook_start", "rejected_candidate"],
        "state_count_per_model": len(profiles),
        "component_names": list(component_names),
        "derivative_steps": list(DERIVATIVE_STEPS),
        "limits": {
            "maximum_absolute_relative_density_delta": VALUE_PARITY_LIMIT,
            "maximum_derivative_relative_change": DERIVATIVE_CHANGE_LIMIT,
            "maximum_repeatability_absolute_delta": REPEATABILITY_LIMIT,
        },
        "reference_note": (
            "DWSIM UNIFAC density values are used as continuity checks, not as "
            "experimental truth. Candidate ranking is limited to the two model profiles."
        ),
        "model_results": results,
        "selected_density_model": selected,
        "classification": (
            "clapeyron_density_model_qualified"
            if passed
            else "no_clapeyron_density_model_qualified"
        ),
        "source_references": [
            "https://clapeyronthermo.github.io/Clapeyron.jl/stable/tutorials/bulk_properties/",
            "https://clapeyronthermo.github.io/Clapeyron.jl/dev/tutorials/basics_model_construction/",
            "https://clapeyronthermo.github.io/Clapeyron.jl/stable/api/association/",
        ],
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "workbook_modified": False,
        "pass_gate": passed,
        "decision": (
            f"authorize_{selected.lower()}_density_only_provider_route"
            if selected
            else "stop_density_route_implementation"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Core V3 water-methanol Clapeyron density qualification",
        "",
        f"- Result: `{report['classification']}`",
        f"- Selected density model: `{report['selected_density_model']}`",
        f"- Decision: `{report['decision']}`",
        f"- States checked per model: `{report['state_count_per_model']}`",
        "- Nonlinear solve or timestep: `False`",
        "- Workbook modified: `False`",
        "",
        "| Model | Max density difference | Median difference | Max derivative change | Pass |",
        "|---|---:|---:|---:|---:|",
    ]
    for result in report["model_results"]:
        lines.append(
            "| "
            f"{result['model']} | "
            f"{result['maximum_absolute_relative_density_delta']:.6e} | "
            f"{result['median_absolute_relative_density_delta']:.6e} | "
            f"{result['maximum_derivative_relative_change']:.6e} | "
            f"{result['pass_gate']} |"
        )
    lines.extend(
        (
            "",
            (
                "DWSIM density is used here as a continuity reference. The selected "
                "model passed positivity, value-parity, repeatability, and two-step "
                "derivative checks over both available column profiles."
            ),
            "",
        )
    )
    return "\n".join(lines)


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
                "selected_density_model": report["selected_density_model"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
