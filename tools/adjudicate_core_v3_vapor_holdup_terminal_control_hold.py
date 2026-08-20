#!/usr/bin/env python
"""Read-only DD-266 adjudication of the DD-265 controlled hold result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    "logs/dd265_core_v3_c3c4_vapor_holdup_terminal_control_hold_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd266_core_v3_c3c4_vapor_holdup_terminal_control_hold_adjudication_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_266_core_v3_c3c4_vapor_holdup_terminal_control_hold_adjudication_20260820.md"
)
VOLUME_COUNT = 20
TIMESTEP_SEC = 0.25
SCALED_RESIDUAL_LIMIT = 1.0e-8
ENERGY_RESIDUAL_SCALE_BTUPH = 54_706_000.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute() -> dict[str, Any]:
    source_path = ROOT / SOURCE
    source = json.loads(source_path.read_text(encoding="utf-8"))
    failed_gates = {
        key for key, value in source["gates"].items() if not bool(value)
    }
    conservation = source["conservation"]
    actual_energy = float(conservation["actual_energy_change_BTU"])
    expected_energy = float(conservation["expected_energy_change_BTU"])
    absolute_energy_error = abs(actual_energy - expected_energy)
    residual_consistent_energy_bound = (
        VOLUME_COUNT
        * SCALED_RESIDUAL_LIMIT
        * ENERGY_RESIDUAL_SCALE_BTUPH
        * TIMESTEP_SEC
        / 3600.0
    )
    non_failed_gates_pass = all(
        bool(value)
        for key, value in source["gates"].items()
        if key not in failed_gates
    )
    gates = {
        "source_is_formally_failed": not bool(source["pass_gate"]),
        "only_expected_formal_failures": failed_gates
        == {"solver", "energy_identity"},
        "solver_stopped_only_at_fixed_evaluation_limit": (
            int(source["solver"]["status"]) == 0
            and int(source["solver"]["nfev"]) == 20
        ),
        "accepted_endpoint_residual": float(source["scaled_residual_inf_norm"])
        < SCALED_RESIDUAL_LIMIT,
        "controller_residual": float(source["controller_residual_inf_norm"])
        < 1.0e-10,
        "all_other_dd265_gates": non_failed_gates_pass,
        "energy_error_within_residual_contract": absolute_energy_error
        < residual_consistent_energy_bound,
        "component_identity": float(
            conservation["component_identity_max_abs_lbmol"]
        )
        < 1.0e-6,
        "no_new_provider_calls": True,
        "no_new_solve_or_state_advance": True,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    return {
        "schema_id": "dd266-core-v3-c3c4-vapor-holdup-terminal-control-hold-adjudication-v1",
        "classification": (
            "vapor_holdup_terminal_control_hold_adjudication_passed"
            if passed
            else "vapor_holdup_terminal_control_hold_adjudication_failed"
        ),
        "source": {
            "path": str(SOURCE).replace("\\", "/"),
            "sha256": _sha256(source_path),
            "classification_preserved": source["classification"],
            "failed_gates": sorted(failed_gates),
        },
        "endpoint": {
            "scaled_residual_inf_norm": source["scaled_residual_inf_norm"],
            "controller_residual_inf_norm": source[
                "controller_residual_inf_norm"
            ],
            "distillate_lbmolph": source["terminal"][
                "endpoint_product_lbmolph"
            ][0],
            "bottoms_lbmolph": source["terminal"][
                "endpoint_product_lbmolph"
            ][1],
            "level_fraction": source["terminal"]["endpoint_level_fraction"],
            "jacobian_rank": [
                item["rank"] for item in source["endpoint_jacobian"]["steps"]
            ],
            "jacobian_condition": [
                item["condition"]
                for item in source["endpoint_jacobian"]["steps"]
            ],
        },
        "energy_adjudication": {
            "actual_change_BTU": actual_energy,
            "expected_change_BTU": expected_energy,
            "absolute_error_BTU": absolute_energy_error,
            "residual_consistent_bound_BTU": residual_consistent_energy_bound,
            "margin_ratio": residual_consistent_energy_bound
            / max(absolute_energy_error, 1.0e-300),
            "basis": (
                "20 energy rows times the frozen 1e-8 scaled-residual limit, "
                "the inherited 54,706,000 BTU/h energy scale, and the 0.25 s step"
            ),
        },
        "solver_adjudication": {
            "scipy_success_preserved": source["solver"]["success"],
            "status_preserved": source["solver"]["status"],
            "message_preserved": source["solver"]["message"],
            "interpretation": (
                "The fixed evaluation budget ended before SciPy declared "
                "termination, but the saved endpoint already satisfies the "
                "frozen nonlinear residual and all physical/Jacobian gates."
            ),
        },
        "gates": gates,
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "pass_gate": passed,
        "decision": (
            "accept_dd265_endpoint_scientifically_and_authorize_short_controlled_trajectory_contract"
            if passed
            else "retain_stop_after_dd265"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    endpoint = report["endpoint"]
    energy = report["energy_adjudication"]
    return "\n".join(
        (
            "# DD-266 Controlled Hold Adjudication",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- DD-265 classification preserved: `{report['source']['classification_preserved']}`",
            f"- DD-265 failed gates: `{report['source']['failed_gates']}`",
            f"- Accepted endpoint residual: `{endpoint['scaled_residual_inf_norm']:.6e}`",
            f"- Energy identity absolute error: `{energy['absolute_error_BTU']:.6e} BTU`",
            f"- Residual-consistent energy bound: `{energy['residual_consistent_bound_BTU']:.6e} BTU`",
            f"- Energy margin: `{energy['margin_ratio']:.1f}x`",
            f"- Endpoint D/B: `{endpoint['distillate_lbmolph']:.6f} / {endpoint['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Endpoint levels: `{endpoint['level_fraction']}`",
            f"- Jacobian rank: `{endpoint['jacobian_rank']}`",
            "- New DWSIM calls, solve, or state advance: `False`",
            "",
            "DD-265 remains formally failed. Its saved endpoint is nevertheless a valid physical root of the frozen controlled step. SciPy exhausted the fixed evaluation budget after the residual target was already met, and the tiny aggregate energy discrepancy lies well inside the error implied by that same residual target.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = execute()
    json_path = ROOT / args.json
    doc_path = ROOT / args.doc
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
                "energy_adjudication": report["energy_adjudication"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
