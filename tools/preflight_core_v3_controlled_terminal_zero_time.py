#!/usr/bin/env python
"""DD-126 development preflight for the controlled-terminal zero-time path."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_controlled_terminal_zero_time as dd125
import audit_core_v3_terminal_gauge_invariance as dd121
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    evaluate_controlled_terminal_zero_time,
)


SOURCE = Path("logs/dd125_core_v3_controlled_terminal_zero_time_contract_20260727.json")
RESULT = Path("logs/dd126_core_v3_controlled_terminal_zero_time_preflight_20260805.json")
DOC = Path("docs/dd_126_core_v3_controlled_terminal_zero_time_preflight_20260805.md")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def main() -> None:
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-126 preflight result already exists")
    payload = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = (
        dd121._context(payload)
    )
    contract = dd125._dynamic_contract(payload)
    point = np.asarray(payload["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(payload["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    started = time.perf_counter()

    seed = evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=TerminalLevelSetpoints(0.5, 0.5),
        solve_coordinates=point,
        state_id="dd126:setpoint_reconstruction",
        evaluation_kind="residual",
        **common,
    )
    setpoints = TerminalLevelSetpoints(*_vector(seed.level_fraction))
    baseline = evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=setpoints,
        solve_coordinates=point,
        state_id="dd126:baseline",
        evaluation_kind="residual",
        **common,
    )
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    steady = baseline.base.pressure_evaluation.base_evaluation.steady_evaluation
    densities = steady.properties.liquid_density_lbmol_ft3
    gates = {
        "complete_50_row_residual": baseline.scaled.shape == (50,),
        "finite_residual": bool(np.all(np.isfinite(baseline.scaled))),
        "stationary_residual": float(np.max(np.abs(baseline.scaled))) < 1.0e-8,
        "controller_rows": float(np.max(np.abs(baseline.scaled[-4:]))) < 1.0e-10,
        "physical_levels": bool(np.all((baseline.level_fraction > 0.01) & (baseline.level_fraction < 0.99))),
        "positive_density": bool(np.all(np.asarray(densities) > 0.0)),
        "bumpless_products": bool(
            abs(baseline.distillate_lbmolph - payload["expected_distillate_lbmolph"])
            / payload["expected_distillate_lbmolph"]
            < 1.0e-10
            and abs(baseline.bottoms_lbmolph - payload["expected_bottoms_lbmolph"])
            / payload["expected_bottoms_lbmolph"]
            < 1.0e-10
        ),
        "provider": provenance["pass"],
        "call_limit": provenance["total_calls"] < 1000,
        "wall_limit": elapsed < 30.0,
        "no_jacobian_solve_or_timestep": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": "dd126-core-v3-controlled-terminal-zero-time-preflight-v1",
        "commit": _git("rev-parse", "HEAD"),
        "source": str(SOURCE).replace("\\", "/"),
        "source_sha256": _sha(ROOT / SOURCE),
        "classification": "dd126_passed" if passed else "dd126_failed",
        "decision": "authorize_frozen_dd127_live_jacobian_contract" if passed else "stop_controlled_terminal_handoff",
        "level_setpoints": asdict(setpoints),
        "liquid_density_lbmol_ft3": _vector(densities),
        "scaled_residual": _vector(baseline.scaled),
        "residual_inf_norm": float(np.max(np.abs(baseline.scaled))),
        "controller_residual_inf_norm": float(np.max(np.abs(baseline.scaled[-4:]))),
        "distillate_lbmolph": baseline.distillate_lbmolph,
        "bottoms_lbmolph": baseline.bottoms_lbmolph,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": passed,
        "jacobian_evaluated": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / DOC).write_text(
        "\n".join(
            (
                "# DD-126 Controlled-Terminal Zero-Time Interface Preflight",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Drum level: `{setpoints.drum_fraction:.6f}` fraction of diameter",
                f"- Sump level: `{setpoints.sump_fraction:.6f}` fraction of height",
                f"- Residual infinity norm: `{result['residual_inf_norm']:.6e}`",
                f"- Controller residual infinity norm: `{result['controller_residual_inf_norm']:.6e}`",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "This was an explicitly authorized development preflight, not a frozen scientific Jacobian campaign. It made no Jacobian, nonlinear-solve, timestep, or dynamic call.",
                "",
            )
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
