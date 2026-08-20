#!/usr/bin/env python
"""Read-only DD-268 adjudication of DD-267's controlled refinement gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    "logs/dd267_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd268_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_adjudication_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_268_core_v3_c3c4_vapor_holdup_terminal_control_short_trajectory_adjudication_20260820.md"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute() -> dict[str, Any]:
    source_path = ROOT / SOURCE
    source = json.loads(source_path.read_text(encoding="utf-8"))
    failed_gates = {
        key for key, value in source["gates"].items() if not bool(value)
    }
    nominal = source["nominal_response"]
    refined = source["refined_response"]
    nominal_actual = np.asarray(nominal["actual_component_change_lbmol"], dtype=float)
    refined_actual = np.asarray(refined["actual_component_change_lbmol"], dtype=float)
    nominal_expected = np.asarray(
        nominal["expected_component_change_lbmol"], dtype=float
    )
    refined_expected = np.asarray(
        refined["expected_component_change_lbmol"], dtype=float
    )
    actual_path_difference = nominal_actual - refined_actual
    expected_path_difference = nominal_expected - refined_expected
    unexplained_component_difference = actual_path_difference - expected_path_difference
    actual_signed_total_difference = float(np.sum(actual_path_difference))
    expected_signed_total_difference = float(np.sum(expected_path_difference))
    refinement = source["refinement"]
    gates = {
        "source_formally_failed": not bool(source["pass_gate"]),
        "only_refinement_failed": failed_gates == {"refinement"},
        "all_non_refinement_gates_passed": all(
            bool(value)
            for key, value in source["gates"].items()
            if key != "refinement"
        ),
        "nominal_component_conservation": float(
            nominal["component_identity_max_abs_lbmol"]
        )
        < 1.0e-6,
        "refined_component_conservation": float(
            refined["component_identity_max_abs_lbmol"]
        )
        < 1.0e-6,
        "path_difference_explained_by_boundary_integration": float(
            np.max(np.abs(unexplained_component_difference))
        )
        < 1.0e-6,
        "signed_difference_explained_by_boundary_integration": abs(
            actual_signed_total_difference - expected_signed_total_difference
        )
        < 1.0e-6,
        "predeclared_component_l1_limit_passed": float(
            refinement["component_l1_lbmol"]
        )
        < 1.0e-4,
        "all_non_inventory_refinement_limits_passed": bool(
            float(refinement["temperature_F"]) < 1.0e-4
            and float(refinement["pressure_psia"]) < 1.0e-4
            and float(refinement["flow_relative"]) < 1.0e-4
            and float(refinement["phase_transfer_scaled"]) < 1.0e-3
            and float(refinement["duty_relative"]) < 1.0e-4
            and float(refinement["level_fraction"]) < 1.0e-6
            and float(refinement["product_relative"]) < 1.0e-5
        ),
        "no_new_provider_calls": True,
        "no_new_solve_or_state_advance": True,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    return {
        "schema_id": "dd268-core-v3-c3c4-vapor-holdup-terminal-control-short-trajectory-adjudication-v1",
        "classification": (
            "controlled_refinement_adjudication_passed"
            if passed
            else "controlled_refinement_adjudication_failed"
        ),
        "source": {
            "path": SOURCE.as_posix(),
            "sha256": _sha256(source_path),
            "classification_preserved": source["classification"],
            "failed_gates": sorted(failed_gates),
        },
        "controller_aware_refinement": {
            "actual_path_component_difference_lbmol": actual_path_difference.tolist(),
            "expected_boundary_component_difference_lbmol": expected_path_difference.tolist(),
            "unexplained_component_difference_lbmol": unexplained_component_difference.tolist(),
            "unexplained_component_max_abs_lbmol": float(
                np.max(np.abs(unexplained_component_difference))
            ),
            "actual_signed_total_difference_lbmol": actual_signed_total_difference,
            "expected_signed_total_difference_lbmol": expected_signed_total_difference,
            "signed_total_explanation_error_lbmol": abs(
                actual_signed_total_difference - expected_signed_total_difference
            ),
            "interpretation": (
                "Nominal and refined backward-Euler paths use slightly different "
                "controller outputs. Their inventory difference is therefore "
                "expected to equal the difference in integrated external D/B flows, "
                "not zero as in the earlier fixed-boundary open-loop gate."
            ),
        },
        "saved_refinement": refinement,
        "saved_performance": {
            "logical_provider_calls": source["logical_provider_calls"],
            "wall_clock_sec": source["wall_clock_sec"],
            "simulation_wall_ratio": source["simulation_wall_ratio"],
        },
        "gates": gates,
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "pass_gate": passed,
        "decision": (
            "accept_dd267_scientifically_and_authorize_longer_controlled_trajectory_contract"
            if passed
            else "retain_stop_after_dd267"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    values = report["controller_aware_refinement"]
    performance = report["saved_performance"]
    return "\n".join(
        (
            "# DD-268 Controlled Refinement Adjudication",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- DD-267 classification preserved: `{report['source']['classification_preserved']}`",
            f"- DD-267 failed gates: `{report['source']['failed_gates']}`",
            f"- Actual signed path difference: `{values['actual_signed_total_difference_lbmol']:.6e} lbmol`",
            f"- Boundary-predicted signed difference: `{values['expected_signed_total_difference_lbmol']:.6e} lbmol`",
            f"- Unexplained component maximum: `{values['unexplained_component_max_abs_lbmol']:.6e} lbmol`",
            f"- Provider calls preserved: `{performance['logical_provider_calls']}`",
            f"- Wall clock preserved: `{performance['wall_clock_sec']:.3f} s`",
            "- New DWSIM calls, solve, or state advance: `False`",
            "",
            values["interpretation"],
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
                "controller_aware_refinement": report[
                    "controller_aware_refinement"
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
