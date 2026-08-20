#!/usr/bin/env python
"""Audit the split liquid/vapor balances at the accepted C3/C4 root."""

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

import audit_core_v3_aligned_pr_density_parity as dd229  # noqa: E402
import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
import run_core_v3_full_c3c4_steady_root as dd223  # noqa: E402

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (  # noqa: E402
    VaporHoldupBalanceInputs,
    evaluate_two_phase_balances,
    evaluate_two_phase_transport,
    stationary_phase_transfer_from_vapor_transport,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    build_column_vapor_geometry,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    audit_vapor_holdup_properties,
    evaluate_vapor_holdup_properties,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


SOURCE_ROOT = Path("logs/dd231_core_v3_full_c3c4_aligned_density_root_20260815.json")
SOURCE_MODEL_CONTRACT = dd223.SOURCE_CONTRACT
DEFAULT_JSON = Path("logs/dd239_core_v3_c3c4_two_phase_balances_20260820.json")
DEFAULT_DOC = Path("docs/dd_239_core_v3_c3c4_two_phase_balances_20260820.md")
COMPONENT_TOLERANCE_LBMOLPH = 1.0e-7
ENERGY_TOLERANCE_BTUPH = 1.0e-4


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def build_report() -> dict[str, Any]:
    source = _load(SOURCE_MODEL_CONTRACT)
    root = _load(SOURCE_ROOT)
    if not root.get("campaign_pass"):
        raise RuntimeError("DD-239 requires the accepted DD-231 root")
    state = root["starts"]["source_mapped_seed"]["state"]
    workbook, dwsim_provider, spec, _reference = dd223._source_model(source)
    case = load_case_from_excel(str(workbook))
    column = build_column_spec_from_case(case)
    geometry = build_column_vapor_geometry(column, case.specs, spec.topology)
    liquid_moles = np.asarray(state["liquid_moles_lbmol"], dtype=float)
    liquid_x = np.asarray(state["liquid_mole_fraction"], dtype=float)
    liquid_inventory = liquid_moles[:, np.newaxis] * liquid_x
    vapor_y = np.vstack(
        (
            np.asarray(state["bubble_vapor_mole_fraction"], dtype=float),
            np.asarray(state["vapor_mole_fraction"], dtype=float),
        )
    )
    temperature = np.asarray(state["temperature_F"], dtype=float)
    pressure = np.asarray(spec.pressure_psia, dtype=float)
    provider = dd229.DensityRoutedProvider(
        dwsim_provider,
        dd092._independent_provider(source),
    )
    call_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    properties = evaluate_vapor_holdup_properties(
        geometry,
        liquid_inventory,
        liquid_x,
        vapor_y,
        temperature,
        pressure,
        provider,
        call_audit,
        state_id="dd239:dd231-accepted-root",
    )
    property_gate = audit_vapor_holdup_properties(properties, call_audit)
    inputs = VaporHoldupBalanceInputs(
        topology=spec.topology,
        feed_component_lbmolph=np.asarray(spec.feed_component_lbmolph, dtype=float),
        feed_enthalpy_BTUph=float(spec.feed_enthalpy_BTUph),
        reflux_lbmolph=float(spec.reflux_lbmolph),
        distillate_lbmolph=float(state["distillate_lbmolph"]),
        bottoms_lbmolph=float(state["bottoms_lbmolph"]),
        condenser_duty_BTUph=float(state["condenser_duty_BTUph"]),
        reboiler_duty_BTUph=float(spec.reboiler_duty_BTUph),
    )
    transport = evaluate_two_phase_transport(
        inputs,
        liquid_x,
        vapor_y,
        state["hydraulic_liquid_flow_lbmolph"],
        state["vapor_flow_lbmolph"],
        properties.liquid_enthalpy_BTU_lbmol,
        properties.vapor_enthalpy_BTU_lbmol,
    )
    phase_transfer = stationary_phase_transfer_from_vapor_transport(transport)
    zero_component_rate = np.zeros_like(liquid_inventory)
    balances = evaluate_two_phase_balances(
        transport,
        zero_component_rate,
        zero_component_rate,
        phase_transfer,
        np.zeros(len(spec.topology.volume_ids)),
    )
    maximum_liquid = float(
        np.max(np.abs(balances.liquid_component_residual_lbmolph))
    )
    maximum_vapor = float(
        np.max(np.abs(balances.vapor_component_residual_lbmolph))
    )
    maximum_total = float(
        np.max(np.abs(balances.total_component_residual_lbmolph))
    )
    maximum_energy = float(np.max(np.abs(balances.energy_residual_BTUph)))
    maximum_transfer = float(np.max(np.abs(phase_transfer)))
    component_telescoping = float(
        np.max(np.abs(balances.global_component_telescoping_error_lbmolph))
    )
    energy_telescoping = abs(float(balances.global_energy_telescoping_error_BTUph))
    passed = bool(
        property_gate.pass_gate
        and maximum_liquid <= COMPONENT_TOLERANCE_LBMOLPH
        and maximum_vapor <= COMPONENT_TOLERANCE_LBMOLPH
        and maximum_total <= COMPONENT_TOLERANCE_LBMOLPH
        and maximum_energy <= ENERGY_TOLERANCE_BTUPH
        and component_telescoping <= 1.0e-10
        and energy_telescoping <= 1.0e-6
        and np.allclose(balances.phase_transfer_cancellation_lbmolph, 0.0)
    )
    volume_summaries = []
    for index, volume in enumerate(spec.topology.volume_ids):
        volume_summaries.append(
            {
                "volume_id": volume,
                "phase_transfer_vapor_to_liquid_lbmolph": [
                    float(value) for value in phase_transfer[index]
                ],
                "maximum_liquid_component_residual_lbmolph": float(
                    np.max(np.abs(balances.liquid_component_residual_lbmolph[index]))
                ),
                "maximum_vapor_component_residual_lbmolph": float(
                    np.max(np.abs(balances.vapor_component_residual_lbmolph[index]))
                ),
                "energy_residual_BTUph": float(balances.energy_residual_BTUph[index]),
            }
        )
    return {
        "schema_id": "dd239-core-v3-c3c4-two-phase-balance-audit-v1",
        "classification": (
            "c3c4_two_phase_zero_rate_balances_passed"
            if passed
            else "c3c4_two_phase_zero_rate_balances_failed"
        ),
        "source_root": str(SOURCE_ROOT).replace("\\", "/"),
        "property_audit": asdict(property_gate),
        "balance_summary": {
            "maximum_liquid_component_residual_lbmolph": maximum_liquid,
            "maximum_vapor_component_residual_lbmolph": maximum_vapor,
            "maximum_total_component_residual_lbmolph": maximum_total,
            "maximum_energy_residual_BTUph": maximum_energy,
            "maximum_absolute_phase_transfer_lbmolph": maximum_transfer,
            "global_component_telescoping_error_lbmolph": component_telescoping,
            "global_energy_telescoping_error_BTUph": energy_telescoping,
            "phase_transfer_cancellation_exact": bool(
                np.all(balances.phase_transfer_cancellation_lbmolph == 0.0)
            ),
        },
        "tolerances": {
            "component_lbmolph": COMPONENT_TOLERANCE_LBMOLPH,
            "energy_BTUph": ENERGY_TOLERANCE_BTUPH,
        },
        "volumes": volume_summaries,
        "provider_call_count": call_audit.record_count,
        "pressure_drop_residual_evaluated": False,
        "francis_residual_evaluated": False,
        "full_258_residual_evaluated": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_full_vapor_holdup_residual_assembly"
            if passed
            else "stop_and_review_two_phase_balance_ownership"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    balance = report["balance_summary"]
    return "\n".join(
        (
            "# DD-239 C3/C4 Two-Phase Zero-Rate Balances",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Maximum liquid component residual: `{balance['maximum_liquid_component_residual_lbmolph']:.6e} lbmol/h`",
            f"- Maximum vapor component residual: `{balance['maximum_vapor_component_residual_lbmolph']:.6e} lbmol/h`",
            f"- Maximum total component residual: `{balance['maximum_total_component_residual_lbmolph']:.6e} lbmol/h`",
            f"- Maximum energy residual: `{balance['maximum_energy_residual_BTUph']:.6e} BTU/h`",
            f"- Component telescoping error: `{balance['global_component_telescoping_error_lbmolph']:.6e} lbmol/h`",
            f"- Energy telescoping error: `{balance['global_energy_telescoping_error_BTUph']:.6e} BTU/h`",
            f"- Exact interphase cancellation: `{balance['phase_transfer_cancellation_exact']}`",
            "",
            "The accepted total balance is split into separate liquid and vapor equations. The stationary vapor equation determines local vapor-to-liquid phase transfer; that same transfer enters the liquid equation with the opposite sign.",
            "",
            "Pressure-drop and Francis rows are not yet assembled into the complete 258-equation residual. No solve, timestep, or integration occurred.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report()
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
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
