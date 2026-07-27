#!/usr/bin/env python
"""Run the property-free DD-118 Core V3 zero-rate feasibility audit."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.zero_rate_feasibility_v1 import (
    audit_zero_rate_feasibility,
)


RESULT = ROOT / "logs/dd118_core_v3_zero_rate_feasibility_20260727.json"
DOC = ROOT / "docs/dd_118_core_v3_zero_rate_feasibility_20260727.md"


def main() -> dict:
    primary = audit_zero_rate_feasibility(("n-Propane", "n-Butane", "n-Pentane"))
    generic = audit_zero_rate_feasibility(("A", "B"))
    passed = primary.pass_gate and generic.pass_gate
    result = {
        "schema_id": "dd118-core-v3-zero-rate-feasibility-result-v1",
        "classification": "dd118_passed" if passed else "dd118_failed",
        "decision": (
            "authorize_frozen_live_zero_rate_readiness_contract"
            if passed
            else "stop_zero_rate_initializer_path"
        ),
        "primary_three_component_audit": asdict(primary),
        "generic_two_component_audit": asdict(generic),
        "interpretation": {
            "all_initializer_targets": "generically_overdetermined_at_zero_rate",
            "global_component_and_energy_targets": "release_from_exact_constraints_and_retain_as_diagnostics",
            "terminal_total_holdups": "retain_as_physical_scale_selection_subject_to_live_rank_audit",
            "zero_rate_dae_core": "square_and_structurally_full_rank",
        },
        "live_property_calls": 0,
        "residual_evaluations": 0,
        "jacobian_evaluations": 0,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass": bool(passed),
    }
    RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    DOC.write_text("\n".join((
        "# DD-118 Core V3 Zero-Rate Feasibility Audit",
        "",
        f"- Classification: `{result['classification']}`",
        f"- Decision: `{result['decision']}`",
        f"- Zero-rate DAE core: `{primary.zero_rate_dae_shape[0]} x {primary.zero_rate_dae_shape[1]}`, rank `{primary.zero_rate_dae_structural_rank}`",
        f"- All-target zero-rate system: `{primary.all_target_shape[0]} x {primary.all_target_shape[1]}`, rank `{primary.all_target_structural_rank}`",
        f"- Surplus exact targets: `{primary.all_target_equation_surplus}`",
        f"- Global targets to release: `{primary.released_global_target_count}`",
        f"- Terminal scale selections retained for live audit: `{primary.terminal_scale_freedom_count}`",
        "- Property/residual/Jacobian/solve/timestep calls: `0/0/0/0/0`",
        "",
        "The current initializer cannot generically impose all component and energy rates equal to zero while preserving every DD-112 global inventory, stored-energy, and terminal-holdup equality. The zero-rate DAE itself is square and structurally viable. A successor should keep the two terminal holdups as physical scale selections, demote the three inherited global component totals and one inherited global energy total to diagnostics, and verify the resulting overdetermined terminal-scaled system numerically before any root solve.",
        "",
    )), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
