#!/usr/bin/env python
"""Audit the DD-086 condenser diagnosis and structural successor."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from audit_core_v2_energy_owned_vapor_numerical import _build_problem
from dynamic_distillation.core_v2.condenser_phase_stability_v1 import (
    audit_fixed_duty_condenser_outlet,
)
from dynamic_distillation.core_v2.condenser_saturated_liquid_registry_v1 import (
    audit_condenser_saturated_liquid_registry,
    build_condenser_saturated_liquid_registry,
)


def _float_list(values) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _phase_payload(audit) -> dict:
    values = asdict(audit)
    values["outlet_overall_composition"] = _float_list(
        audit.outlet_overall_composition
    )
    values["equilibrium_K"] = _float_list(audit.equilibrium_K)
    return values


def _block_counts(entries) -> dict[str, int]:
    result: dict[str, int] = {}
    for entry in entries:
        result[entry.block] = result.get(entry.block, 0) + 1
    return result


def _render(report: dict) -> str:
    phase = report["dd085_fixed_duty_phase_diagnostic"]
    structural = report["successor_structural_audit"]
    return "\n".join(
        (
            "# DD-086 Condenser Phase-Stability Architecture Audit",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Runtime: `{report['wall_clock_sec']:.3f} s`",
            f"- Nonlinear solve attempted: `{report['nonlinear_solve_attempted']}`",
            f"- Dynamic integration attempted: `{report['dynamic_integration_attempted']}`",
            "",
            "## DD-085 Outlet Diagnosis",
            "",
            f"- DWSIM phase classification: `{phase['phase_classification']}`",
            f"- Rachford-Rice vapor fraction: `{phase['vapor_fraction']:.12g}`",
            f"- Stable single liquid: `{phase['stable_single_liquid']}`",
            f"- Imposed liquid enthalpy error: "
            f"`{phase['enthalpy_error_BTU_lbmol']:.6e} BTU/lbmol`",
            "",
            "## Structural Successor",
            "",
            f"- Unknowns/residuals: `{structural['unknown_count']} / "
            f"{structural['residual_count']}`",
            f"- Structural rank: `{structural['structural_rank']}`",
            f"- Structural nullity: `{structural['structural_nullity']}`",
            f"- Solved condenser-duty unknowns: "
            f"`{structural['condenser_duty_unknown_count']}`",
            f"- Incipient-vapor coordinates: "
            f"`{structural['condenser_incipient_vapor_coordinate_count']}`",
            f"- Bubble-fugacity equations: "
            f"`{structural['condenser_bubble_equation_count']}`",
            f"- Pass: `{structural['pass_gate']}`",
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )


def run(
    dd085_result_path: Path,
    out_prefix: Path,
) -> dict:
    started = time.perf_counter()
    dd085 = json.loads(dd085_result_path.read_text(encoding="utf-8"))
    if dd085.get("classification") != "dd085_energy_owned_steady_root_failed":
        raise RuntimeError("DD-086 requires the preserved DD-085 failed result")
    canonical = dd085["starts"]["canonical_role_mapped_seed"]
    provider, spec, _reference, source, _operating = _build_problem(
        Path(dd085["workbook"]),
        str(dd085["property_package"]),
    )
    temperature = np.asarray(canonical["temperature_F"], dtype=float)
    pressure = np.asarray(source["pressure_psia"], dtype=float)
    liquid_x = np.asarray(canonical["liquid_mole_fraction"], dtype=float)
    vapor_y = np.asarray(canonical["vapor_mole_fraction"], dtype=float)
    vapor_flow = np.asarray(canonical["vapor_flow_lbmolph"], dtype=float)
    phase_audit = audit_fixed_duty_condenser_outlet(
        provider,
        inlet_temperature_F=float(temperature[1]),
        inlet_pressure_psia=float(pressure[1]),
        inlet_vapor_composition=vapor_y[0],
        outlet_temperature_F=float(temperature[0]),
        outlet_pressure_psia=float(pressure[0]),
        outlet_overall_composition=liquid_x[0],
        overhead_vapor_flow_lbmolph=float(vapor_flow[-1]),
        condenser_duty_BTUph=float(spec.condenser_duty_BTUph),
    )

    registry = build_condenser_saturated_liquid_registry(spec.component_names)
    structural_audit = audit_condenser_saturated_liquid_registry(registry)
    phase_diagnosis_pass = bool(
        phase_audit.phase_classification == "vapor"
        and phase_audit.vapor_fraction >= 1.0 - 1.0e-8
        and not phase_audit.stable_single_liquid
        and abs(phase_audit.enthalpy_error_BTU_lbmol) < 1.0e-8
    )
    passed = bool(phase_diagnosis_pass and structural_audit.pass_gate)
    report = {
        "schema_id": "dd086-core-v2-condenser-phase-stability-architecture-v1",
        "classification": (
            "dd086_condenser_phase_stable_structure_passed"
            if passed
            else "dd086_condenser_phase_stable_structure_failed"
        ),
        "decision": (
            "authorize_one_frozen_live_40x40_numerical_audit"
            if passed
            else "freeze_core_v2_at_dd085"
        ),
        "authorization": (
            "DD-086 passes structurally. One frozen live-property numerical "
            "audit of the 40 x 40 solved-duty saturated-liquid formulation "
            "may be designed next. No nonlinear root solve or dynamic "
            "integration is authorized."
            if passed
            else "DD-086 failed its structural gate. Freeze Core V2 at "
            "DD-085; do not repair the registry by tuning equations."
        ),
        "dd085_result": str(dd085_result_path.resolve()),
        "dd085_contract_commit": dd085["contract_commit"],
        "property_package": str(dd085["property_package"]),
        "component_names": list(spec.component_names),
        "dd085_fixed_duty_phase_diagnostic": _phase_payload(phase_audit),
        "phase_diagnosis_pass": phase_diagnosis_pass,
        "selected_successor": {
            "condenser_type": "inventory_free_total_condenser",
            "outlet_specification": "saturated_liquid_beta_zero",
            "condenser_duty_ownership": "algebraic_unknown",
            "drum_temperature_ownership": (
                "condenser_bubble_fugacity_and_drum_energy_balance"
            ),
            "fixed_duty_total_condenser_retained": False,
            "partial_condenser_vapor_outlet_present": False,
            "specified_subcooling_present": False,
        },
        "unknown_block_counts": _block_counts(registry.unknowns),
        "residual_block_counts": _block_counts(registry.residuals),
        "unknown_names": [entry.name for entry in registry.unknowns],
        "residual_names": [entry.name for entry in registry.residuals],
        "external_parameters": list(registry.external_parameters),
        "successor_structural_audit": asdict(structural_audit),
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "continuation_or_solver_tuning_attempted": False,
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    out_prefix.with_suffix(".md").write_text(
        _render(report),
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dd085-result",
        type=Path,
        default=Path("logs/dd085_energy_owned_steady_root_20260718.json"),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path(
            "logs/dd086_condenser_phase_stable_architecture_20260718"
        ),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(args.dd085_result, args.out_prefix)
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "decision": result["decision"],
                "wall_clock_sec": result["wall_clock_sec"],
            },
            indent=2,
        )
    )
    raise SystemExit(
        0
        if result["classification"]
        == "dd086_condenser_phase_stable_structure_passed"
        else 2
    )
