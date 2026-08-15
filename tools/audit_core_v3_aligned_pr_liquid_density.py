#!/usr/bin/env python
"""Audit a phase-explicit aligned-PR liquid density against DD-227 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_provider_governed_numerical as dd092


SOURCE = Path("logs/dd227_core_v3_dd223_hydraulic_derivative_20260815.json")
SOURCE_CONTRACT = Path(
    "logs/dd227_core_v3_dd223_hydraulic_derivative_contract_20260815.json"
)
RESULT = Path("logs/dd228_core_v3_aligned_pr_liquid_density_20260815")
SCHEMA = "dd228-core-v3-aligned-pr-liquid-density-v1"


def _candidate(
    provider: Any,
    pressure_psia: float,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    temperature = float(snapshot["temperature_F"])
    composition = np.asarray(snapshot["liquid_mole_fraction"], dtype=float)
    roots = provider.phase_compressibility_roots(
        temperature, pressure_psia, composition
    )
    density = provider.liquid_density_lbmol_ft3(
        temperature, pressure_psia, composition
    )
    dwsim_density = float(snapshot["liquid_density_lbmol_ft3"])
    return {
        "temperature_F": temperature,
        "compressibility_roots": roots.tolist(),
        "selected_liquid_root": float(roots[0]),
        "candidate_density_lbmol_ft3": float(density),
        "saved_dwsim_density_lbmol_ft3": dwsim_density,
        "candidate_minus_dwsim_density_lbmol_ft3": float(density - dwsim_density),
        "candidate_dwsim_relative_difference": float(
            (density - dwsim_density) / dwsim_density
        ),
    }


def run(source_path: Path = SOURCE, out_prefix: Path = RESULT) -> dict[str, Any]:
    source = json.loads((ROOT / source_path).read_text(encoding="utf-8"))
    contract = json.loads((ROOT / SOURCE_CONTRACT).read_text(encoding="utf-8"))
    model_contract = json.loads(
        (ROOT / contract["source_model_contract"]).read_text(encoding="utf-8")
    )
    if not source.get("pass_gate"):
        raise RuntimeError("DD-228 requires the passing DD-227 evidence")
    provider = dd092._independent_provider(model_contract)
    owner = contract["target_owner"]
    owner_index = model_contract["source_mapping"]["roles"].index(owner)
    pressure = float(model_contract["source_mapping"]["pressure_psia"][owner_index])
    endpoints: dict[str, Any] = {}
    all_smooth = True
    all_physical = True
    for name, endpoint in source["endpoints"].items():
        baseline = _candidate(provider, pressure, endpoint["baseline"])
        steps = []
        density_derivatives = []
        for item in endpoint["steps"]:
            plus = _candidate(provider, pressure, item["plus"])
            minus = _candidate(provider, pressure, item["minus"])
            step = float(item["step"])
            derivative = (
                plus["candidate_density_lbmol_ft3"]
                - minus["candidate_density_lbmol_ft3"]
            ) / (2.0 * step)
            density_derivatives.append(derivative)
            steps.append(
                {
                    "step": step,
                    "candidate_density_derivative_per_F": float(derivative),
                    "plus": plus,
                    "minus": minus,
                }
            )
        derivatives = np.asarray(density_derivatives, dtype=float)
        derivative_spread = float(
            (np.max(derivatives) - np.min(derivatives))
            / max(abs(float(np.mean(derivatives))), 1.0e-15)
        )
        endpoint_smooth = bool(derivative_spread < 1.0e-4)
        endpoint_physical = bool(
            baseline["candidate_density_lbmol_ft3"] > 0.0
            and all(
                item[side]["candidate_density_lbmol_ft3"] > 0.0
                and item[side]["selected_liquid_root"] > 0.0
                for item in steps
                for side in ("plus", "minus")
            )
        )
        all_smooth = all_smooth and endpoint_smooth
        all_physical = all_physical and endpoint_physical
        endpoints[name] = {
            "pressure_psia": pressure,
            "baseline": baseline,
            "steps": steps,
            "candidate_density_derivative_relative_spread": derivative_spread,
            "smooth": endpoint_smooth,
            "physical": endpoint_physical,
        }
    pass_gate = bool(all_smooth and all_physical)
    report = {
        "schema_id": SCHEMA,
        "classification": (
            "aligned_pr_liquid_density_feasible"
            if pass_gate else "aligned_pr_liquid_density_not_feasible"
        ),
        "decision": (
            "authorize_one_frozen_governing_density_parity_audit"
            if pass_gate else "stop_aligned_pr_density_path"
        ),
        "target_owner": owner,
        "selection_rule": "smallest_positive_PR_compressibility_root",
        "endpoints": endpoints,
        "model_calls": 0,
        "dwsim_provider_calls": 0,
        "solver_calls": 0,
        "timestep_calls": 0,
        "dynamic_integration_calls": 0,
        "pass_gate": pass_gate,
    }
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-prefix", type=Path, default=RESULT)
    args = parser.parse_args()
    report = run(args.source, args.out_prefix)
    print(json.dumps(report, indent=2))
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
