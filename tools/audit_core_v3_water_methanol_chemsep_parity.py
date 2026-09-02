#!/usr/bin/env python
"""Split ChemSep/Core V3 disagreement into independent physical ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from audit_core_v3_water_methanol_starting_state import (  # noqa: E402
    DEFAULT_WORKBOOK,
    PROPERTY_PACKAGE,
    build_problem,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
)


DEFAULT_JSON = Path("logs/core_v3_water_methanol_chemsep_parity_20260901.json")
DEFAULT_DOC = Path("docs/core_v3_water_methanol_chemsep_parity_20260901.md")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _floats(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(values)]


def build_report(workbook: Path = DEFAULT_WORKBOOK) -> dict[str, Any]:
    problem = build_problem(workbook, density_model="VTPR")
    contract = problem["contract"]
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    evaluation = evaluate_vapor_holdup_stationary_residual(
        contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        problem["provider"],
        audit,
        np.zeros(len(contract.variables)),
        state_id="water_methanol:chemsep_parity",
        evaluation_kind="residual",
    )

    source = problem["source"]
    topology = problem["spec"].topology
    volume_index = {volume: index for index, volume in enumerate(topology.volume_ids)}
    actual_drop = np.asarray(
        [
            evaluation.endpoint.pressure_psia[volume_index[source_volume]]
            - evaluation.endpoint.pressure_psia[volume_index[destination_volume]]
            for source_volume, destination_volume, _symbol in topology.vapor_links
        ],
        dtype=float,
    )
    liquid_drop = evaluation.pressure_drop.liquid_head_drop_psia
    dry_drop = evaluation.pressure_drop.dry_tray_drop_psia
    base_coefficient = float(problem["numerical"].dry_tray_pressure_drop_coefficient)
    required_coefficient = base_coefficient * (actual_drop - liquid_drop) / dry_drop

    liquid_flow = evaluation.endpoint.hydraulic_liquid_flow_lbmolph
    calculated_liquid_flow = liquid_flow - evaluation.francis_residual_lbmolph
    liquid_relative_error = evaluation.francis_residual_lbmolph / liquid_flow

    fugacity_log = evaluation.fugacity_residual
    terminal_mask = np.ones_like(fugacity_log, dtype=bool)
    terminal_mask[[0, -1], :] = False
    interior_abs = np.abs(fugacity_log[terminal_mask])
    maximum_interior_log = float(np.max(interior_abs))
    maximum_interior_ratio_error = float(np.expm1(maximum_interior_log))

    x = np.asarray(source["liquid_mole_fraction"], dtype=float)
    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    distillate = float(source["distillate_reference_lbmolph"])
    bottoms = float(source["bottoms_reference_lbmolph"])
    external_component = feed_component - distillate * x[0] - bottoms * x[-1]
    global_energy_residual = float(np.sum(evaluation.balances.energy_residual_BTUph))
    required_condenser_duty = float(
        evaluation.endpoint.condenser_duty_BTUph + global_energy_residual
    )

    properties = evaluation.properties
    liquid_volume = properties.free_volume.liquid_volume_ft3
    geometry = problem["geometry"]
    terminal_capacity = np.asarray(
        (
            geometry[0].gross_capacity_ft3 - geometry[0].fixed_vapor_extension_ft3,
            geometry[-1].gross_capacity_ft3 - geometry[-1].fixed_vapor_extension_ft3,
        ),
        dtype=float,
    )
    terminal_level = np.asarray((liquid_volume[0], liquid_volume[-1])) / terminal_capacity

    pressure_rows = []
    for index, (source_volume, destination_volume, symbol) in enumerate(topology.vapor_links):
        pressure_rows.append(
            {
                "link": f"{source_volume}->{destination_volume}",
                "symbol": symbol,
                "actual_drop_psia": float(actual_drop[index]),
                "liquid_head_drop_psia": float(liquid_drop[index]),
                "dry_tray_drop_at_base_coefficient_psia": float(dry_drop[index]),
                "equation_residual_psia": float(evaluation.pressure_drop.residual_psia[index]),
                "required_dry_tray_coefficient": float(required_coefficient[index]),
            }
        )

    hydraulic_rows = []
    for index, volume in enumerate(topology.hydraulic_volume_ids):
        hydraulic_rows.append(
            {
                "volume": volume,
                "chemsep_liquid_flow_lbmolph": float(liquid_flow[index]),
                "francis_calculated_liquid_flow_lbmolph": float(calculated_liquid_flow[index]),
                "residual_lbmolph": float(evaluation.francis_residual_lbmolph[index]),
                "relative_residual": float(liquid_relative_error[index]),
            }
        )

    workbook_path = problem["workbook"]
    top_bubble = problem["top_bubble"]
    bottom_bubble = problem["bottom_bubble"]
    provider_report = audit.report()
    pressure_single_coefficient_compatible = bool(
        np.max(required_coefficient) / np.min(required_coefficient) <= 1.10
    )
    interior_vle_close = bool(maximum_interior_log <= 0.02)
    global_material_close = bool(np.max(np.abs(external_component)) <= 0.2)
    global_energy_close = bool(abs(global_energy_residual) <= 0.001 * abs(source["condenser_duty_BTUph"]))

    return {
        "schema_id": "core-v3-chemsep-parity-audit-v1",
        "classification": "parity_not_established",
        "workbook": str(workbook_path),
        "workbook_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        "components": list(problem["spec"].component_names),
        "bulk_property_provider": f"dwsim_{PROPERTY_PACKAGE}",
        "liquid_density_provider": "clapeyron_vtpr",
        "terminal_semantics_repair": {
            "scope": "total terminal phase mapping; no component names or fitted component constants",
            "top_temperature_workbook_F": float(problem["source_top_temperature_F"]),
            "top_temperature_reconstructed_F": float(top_bubble.temperature_F),
            "top_temperature_change_F": float(
                top_bubble.temperature_F - problem["source_top_temperature_F"]
            ),
            "top_reconstructed_vapor_mole_fraction": _floats(top_bubble.vapor_mole_fraction),
            "bottom_temperature_workbook_F": float(problem["source_bottom_temperature_F"]),
            "bottom_temperature_reconstructed_F": float(bottom_bubble.temperature_F),
            "bottom_temperature_change_F": float(
                bottom_bubble.temperature_F - problem["source_bottom_temperature_F"]
            ),
            "bottom_workbook_vapor_mole_fraction": _floats(
                np.asarray(source["vapor_mole_fraction"])[-1]
            ),
            "bottom_reconstructed_vapor_mole_fraction": _floats(
                bottom_bubble.vapor_mole_fraction
            ),
            "reason": (
                "A total condenser and a total reboiler do not supply independent "
                "resident-vapor states. Their equilibrium vapor states are reconstructed "
                "from terminal liquid composition and pressure."
            ),
        },
        "thermodynamic_equilibrium": {
            "log_fugacity_residual_by_stage_component": _rows(fugacity_log),
            "maximum_interior_abs_log_fugacity_residual": maximum_interior_log,
            "maximum_interior_fugacity_ratio_error": maximum_interior_ratio_error,
            "maximum_terminal_abs_log_fugacity_residual_after_reconstruction": float(
                np.max(np.abs(fugacity_log[[0, -1], :]))
            ),
            "interior_close_gate": interior_vle_close,
            "meaning": (
                "Terminal placeholder error is removed. Remaining interior mismatch is "
                "a bulk VLE/provider disagreement, not a density-model issue."
            ),
        },
        "pressure_drop": {
            "base_dry_tray_coefficient": base_coefficient,
            "rows": pressure_rows,
            "maximum_abs_residual_psia": float(
                np.max(np.abs(evaluation.pressure_drop.residual_psia))
            ),
            "required_coefficient_minimum": float(np.min(required_coefficient)),
            "required_coefficient_maximum": float(np.max(required_coefficient)),
            "single_coefficient_compatible_gate": pressure_single_coefficient_compatible,
            "meaning": (
                "The workbook pressure profile is prescribed nearly uniformly. It cannot "
                "be reproduced by the present hydraulic equation with one dry-tray coefficient."
            ),
        },
        "liquid_hydraulics": {
            "rows": hydraulic_rows,
            "maximum_abs_residual_lbmolph": float(
                np.max(np.abs(evaluation.francis_residual_lbmolph))
            ),
            "maximum_abs_relative_residual": float(np.max(np.abs(liquid_relative_error))),
        },
        "material_closure": {
            "feed_component_lbmolph": _floats(feed_component),
            "chemsep_distillate_lbmolph": distillate,
            "chemsep_bottoms_lbmolph": bottoms,
            "external_component_residual_lbmolph": _floats(external_component),
            "maximum_local_component_residual_lbmolph": float(
                np.max(np.abs(evaluation.balances.total_component_residual_lbmolph))
            ),
            "global_close_gate": global_material_close,
        },
        "energy_closure": {
            "chemsep_condenser_duty_BTUph": float(source["condenser_duty_BTUph"]),
            "chemsep_reboiler_duty_BTUph": float(source["reboiler_duty_BTUph"]),
            "core_property_global_stationary_residual_BTUph": global_energy_residual,
            "condenser_duty_required_with_fixed_chemsep_state_BTUph": required_condenser_duty,
            "required_condenser_duty_change_BTUph": global_energy_residual,
            "maximum_local_energy_residual_BTUph": float(
                np.max(np.abs(evaluation.balances.energy_residual_BTUph))
            ),
            "global_close_gate": global_energy_close,
        },
        "terminal_inventory_translation": {
            "liquid_moles_lbmol": [
                float(np.sum(evaluation.endpoint.liquid_component_inventory_lbmol[0])),
                float(np.sum(evaluation.endpoint.liquid_component_inventory_lbmol[-1])),
            ],
            "liquid_density_lbmol_ft3": [
                float(properties.liquid_density_lbmol_ft3[0]),
                float(properties.liquid_density_lbmol_ft3[-1]),
            ],
            "calculated_level_fraction": _floats(terminal_level),
            "workbook_nominal_level_fraction": [0.5, 0.5],
            "meaning": (
                "Molar holdups match the workbook targets; level disagreement comes from "
                "density and vessel-volume translation."
            ),
        },
        "provider_calls": {
            "preparation": problem["preparation_audit"].record_count,
            "audit_residual": audit.record_count,
            "fallback_attempted": audit.fallback_attempted,
            "pass_gate": bool(provider_report["pass"] and not audit.fallback_attempted),
        },
        "decision": {
            "repair_applied": "generic total-reboiler resident-vapor reconstruction",
            "do_not_apply": (
                "Do not tune a water-methanol-specific pressure coefficient or force the "
                "ChemSep product split into the governing equations."
            ),
            "next_gate": (
                "separate prescribed-pressure steady-state parity from free-pressure "
                "dynamic initialization, then qualify the bulk VLE/enthalpy provider"
            ),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    thermo = report["thermodynamic_equilibrium"]
    pressure = report["pressure_drop"]
    hydraulics = report["liquid_hydraulics"]
    material = report["material_closure"]
    energy = report["energy_closure"]
    terminal = report["terminal_semantics_repair"]
    levels = report["terminal_inventory_translation"]
    lines = [
        "# Core V3 / ChemSep parity audit",
        "",
        f"- Result: `{report['classification']}`",
        f"- Workbook: `{Path(report['workbook']).name}`",
        f"- Bulk properties: `{report['bulk_property_provider']}`",
        f"- Density only: `{report['liquid_density_provider']}`",
        "",
        "## What the repair changed",
        "",
        "Core V3 now reconstructs the resident equilibrium vapor at both total terminals. "
        "The last ChemSep vapor row is a boundary placeholder, so it is no longer treated "
        "as an independent reboiler vapor state. No component-specific equation or constant was added.",
        "",
        f"- Bottom workbook temperature: `{terminal['bottom_temperature_workbook_F']:.6f} F`",
        f"- Current-provider bottom bubble temperature: `{terminal['bottom_temperature_reconstructed_F']:.6f} F`",
        f"- Change needed for current-provider equilibrium: `{terminal['bottom_temperature_change_F']:+.6f} F`",
        "",
        "## Independent closure results",
        "",
        f"- Interior VLE: maximum log-fugacity mismatch `{thermo['maximum_interior_abs_log_fugacity_residual']:.6f}` "
        f"(`{100.0 * thermo['maximum_interior_fugacity_ratio_error']:.3f}%` as a fugacity-ratio error).",
        f"- Pressure: maximum equation mismatch `{pressure['maximum_abs_residual_psia']:.6f} psia`; "
        f"required link coefficients span `{pressure['required_coefficient_minimum']:.3f}` to "
        f"`{pressure['required_coefficient_maximum']:.3f}`.",
        f"- Liquid hydraulics: maximum Francis mismatch `{hydraulics['maximum_abs_residual_lbmolph']:.3f} lbmol/h` "
        f"(`{100.0 * hydraulics['maximum_abs_relative_residual']:.3f}%`).",
        f"- Material: global component residual `{max(abs(v) for v in material['external_component_residual_lbmolph']):.6f} lbmol/h`; gate `{material['global_close_gate']}`.",
        f"- Energy: global residual `{energy['core_property_global_stationary_residual_BTUph']:.3f} BTU/h`; "
        f"current properties require `Qc={energy['condenser_duty_required_with_fixed_chemsep_state_BTUph']:.3f} BTU/h` at the fixed ChemSep state.",
        f"- Levels from the same terminal molar holdups: top `{100.0 * levels['calculated_level_fraction'][0]:.3f}%`, "
        f"bottom `{100.0 * levels['calculated_level_fraction'][1]:.3f}%` versus workbook nominal `50% / 50%`.",
        "",
        "## Decision",
        "",
        "The short dynamic run did not validate ChemSep parity; it validated a stationary root of the current model. "
        "The workbook product material balance itself closes, but its prescribed pressure profile, its VLE/enthalpy "
        "model, and the present free-pressure hydraulic equations are not one common stationary problem.",
        "",
        "Do not fit a water-methanol-only correction. The next gate is to run two clearly separated modes: "
        "a prescribed-pressure steady-state parity check for thermodynamics and products, and a free-pressure "
        "dynamic initialization check for hydraulics. The bulk VLE/enthalpy provider must then be qualified against "
        "the ChemSep model before another long dynamic run.",
        "",
        "## Pressure-link detail",
        "",
        "| Link | Actual dP (psia) | Liquid head | Dry drop at K=40 | Residual | Required K |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in pressure["rows"]:
        lines.append(
            f"| {row['link']} | {row['actual_drop_psia']:.6f} | "
            f"{row['liquid_head_drop_psia']:.6f} | "
            f"{row['dry_tray_drop_at_base_coefficient_psia']:.6f} | "
            f"{row['equation_residual_psia']:.6f} | "
            f"{row['required_dry_tray_coefficient']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Liquid-hydraulic detail",
            "",
            "| Volume | ChemSep L (lbmol/h) | Francis L (lbmol/h) | Residual | Relative |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in hydraulics["rows"]:
        lines.append(
            f"| {row['volume']} | {row['chemsep_liquid_flow_lbmolph']:.3f} | "
            f"{row['francis_calculated_liquid_flow_lbmolph']:.3f} | "
            f"{row['residual_lbmolph']:.3f} | {100.0 * row['relative_residual']:.3f}% |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report(args.workbook)
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["decision"], indent=2))
    print(f"json={json_path}")
    print(f"doc={doc_path}")


if __name__ == "__main__":
    main()
