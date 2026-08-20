#!/usr/bin/env python
"""Audit live vapor inventory and two-phase energy at the accepted C3/C4 root."""

from __future__ import annotations

import argparse
from dataclasses import asdict
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

import audit_core_v3_aligned_pr_density_parity as dd229  # noqa: E402
import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
import run_core_v3_full_c3c4_steady_root as dd223  # noqa: E402

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    audit_vapor_geometry,
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
DEFAULT_JSON = Path("logs/dd238_core_v3_c3c4_vapor_holdup_properties_20260820.json")
DEFAULT_DOC = Path("docs/dd_238_core_v3_c3c4_vapor_holdup_properties_20260820.md")


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _float_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def build_report() -> dict[str, Any]:
    source = _load(SOURCE_MODEL_CONTRACT)
    root = _load(SOURCE_ROOT)
    if not root.get("campaign_pass"):
        raise RuntimeError("DD-238 requires the accepted DD-231 root")
    state = root["starts"]["source_mapped_seed"]["state"]
    workbook, dwsim_provider, spec, _reference = dd223._source_model(source)
    case = load_case_from_excel(str(workbook))
    column = build_column_spec_from_case(case)
    geometry = build_column_vapor_geometry(column, case.specs, spec.topology)
    geometry_audit = audit_vapor_geometry(geometry, spec.topology)
    if not geometry_audit.pass_gate:
        raise RuntimeError("DD-238 requires the passing DD-237 geometry mapping")

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
    aligned_pr = dd092._independent_provider(source)
    provider = dd229.DensityRoutedProvider(dwsim_provider, aligned_pr)
    call_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={
            "declared_liquid_density": "aligned_pr",
        },
    )
    evaluation = evaluate_vapor_holdup_properties(
        geometry,
        liquid_inventory,
        liquid_x,
        vapor_y,
        temperature,
        pressure,
        provider,
        call_audit,
        state_id="dd238:dd231-accepted-root",
        evaluation_kind="residual",
    )
    property_audit = audit_vapor_holdup_properties(evaluation, call_audit)
    density_routes = {
        record.provider_interface
        for record in call_audit.records
        if record.quantity == "liquid_density"
    }
    dwsim_routes = {
        record.provider_interface
        for record in call_audit.records
        if record.quantity in {"phase_enthalpy", "vapor_compressibility_factor"}
    }
    provider_routing_pass = bool(
        density_routes == {"aligned_pr.declared_liquid_density"}
        and dwsim_routes
        == {
            "dwsim.declared_phase_enthalpy",
            "dwsim.declared_vapor_compressibility_factor",
        }
    )
    reconstructed_y = (
        evaluation.vapor_component_inventory_lbmol
        / evaluation.vapor_moles_lbmol[:, np.newaxis]
    )
    composition_error = float(np.max(np.abs(reconstructed_y - vapor_y)))
    passed = bool(
        geometry_audit.pass_gate
        and property_audit.pass_gate
        and provider_routing_pass
        and composition_error <= 1.0e-14
    )
    volumes = []
    for index, volume in enumerate(evaluation.volume_ids):
        volumes.append(
            {
                "volume_id": volume,
                "temperature_F": float(temperature[index]),
                "pressure_psia": float(pressure[index]),
                "gross_capacity_ft3": float(
                    evaluation.free_volume.gross_capacity_ft3[index]
                ),
                "liquid_volume_ft3": float(
                    evaluation.free_volume.liquid_volume_ft3[index]
                ),
                "free_vapor_volume_ft3": float(
                    evaluation.free_volume.free_vapor_volume_ft3[index]
                ),
                "liquid_density_lbmol_ft3": float(
                    evaluation.liquid_density_lbmol_ft3[index]
                ),
                "vapor_compressibility_factor": float(
                    evaluation.vapor_compressibility_factor[index]
                ),
                "vapor_moles_lbmol": float(evaluation.vapor_moles_lbmol[index]),
                "vapor_component_inventory_lbmol": _float_list(
                    evaluation.vapor_component_inventory_lbmol[index]
                ),
                "liquid_stored_energy_BTU": float(
                    evaluation.liquid_stored_energy_BTU[index]
                ),
                "vapor_stored_energy_BTU": float(
                    evaluation.vapor_stored_energy_BTU[index]
                ),
                "total_stored_energy_BTU": float(
                    evaluation.total_stored_energy_BTU[index]
                ),
                "eos_volume_residual_ft3": float(
                    evaluation.eos_volume_residual_ft3[index]
                ),
            }
        )
    total_liquid = float(np.sum(liquid_inventory))
    total_vapor = float(np.sum(evaluation.vapor_moles_lbmol))
    return {
        "schema_id": "dd238-core-v3-c3c4-vapor-holdup-properties-v1",
        "classification": (
            "c3c4_vapor_holdup_property_reconstruction_passed"
            if passed
            else "c3c4_vapor_holdup_property_reconstruction_failed"
        ),
        "source_root": str(SOURCE_ROOT).replace("\\", "/"),
        "source_root_sha256": _sha256(ROOT / SOURCE_ROOT),
        "source_model_contract": str(SOURCE_MODEL_CONTRACT).replace("\\", "/"),
        "source_model_contract_sha256": _sha256(ROOT / SOURCE_MODEL_CONTRACT),
        "workbook": str(Path(workbook).resolve()),
        "workbook_sha256": _sha256(Path(workbook)),
        "component_names": list(column.components_excel),
        "geometry_audit": asdict(geometry_audit),
        "property_audit": asdict(property_audit),
        "provider_routing": {
            "liquid_density": sorted(density_routes),
            "vapor_z_and_phase_enthalpy": sorted(dwsim_routes),
            "pass_gate": provider_routing_pass,
        },
        "inventory_summary": {
            "total_liquid_moles_lbmol": total_liquid,
            "total_vapor_moles_lbmol": total_vapor,
            "vapor_to_liquid_mole_ratio": total_vapor / total_liquid,
            "maximum_reconstructed_y_error": composition_error,
            "total_liquid_stored_energy_BTU": float(
                np.sum(evaluation.liquid_stored_energy_BTU)
            ),
            "total_vapor_stored_energy_BTU": float(
                np.sum(evaluation.vapor_stored_energy_BTU)
            ),
        },
        "volumes": volumes,
        "property_calls": [asdict(record) for record in call_audit.records],
        "full_two_phase_dae_residual_evaluated": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_two_phase_vapor_holdup_residual_implementation"
            if passed
            else "stop_vapor_holdup_successor"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    inventory = report["inventory_summary"]
    audit = report["property_audit"]
    return "\n".join(
        (
            "# DD-238 C3/C4 Vapor-Holdup Live Properties",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Physical volumes: `{audit['volume_count']}`",
            f"- Audited property calls: `{audit['provider_call_count']}`",
            f"- Total liquid inventory: `{inventory['total_liquid_moles_lbmol']:.6f} lbmol`",
            f"- Reconstructed vapor inventory: `{inventory['total_vapor_moles_lbmol']:.6f} lbmol`",
            f"- Vapor/liquid mole ratio: `{inventory['vapor_to_liquid_mole_ratio']:.6e}`",
            f"- Minimum free vapor volume: `{audit['minimum_free_vapor_volume_ft3']:.6f} ft3`",
            f"- Minimum vapor Z: `{audit['minimum_vapor_compressibility_factor']:.6f}`",
            f"- Maximum relative EOS residual: `{audit['maximum_relative_eos_residual']:.3e}`",
            "",
            "DWSIM supplied vapor compressibility and liquid/vapor enthalpy. The accepted aligned-PR route supplied liquid density. No fallback was allowed.",
            "",
            "This audit reconstructed resident vapor component inventories and included both liquid and vapor stored energy. It did not evaluate the full successor residual, solve an equation system, take a timestep, or run a trajectory.",
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
