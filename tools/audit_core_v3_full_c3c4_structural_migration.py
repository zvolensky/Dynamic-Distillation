#!/usr/bin/env python
"""Audit the property-free Core V3 migration to the full C3/C4 column."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    audit_provider_governed_registry,
    build_column_topology,
    build_provider_governed_registry,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_contract_v1 import (
    audit_controlled_bdf2_contract,
    build_controlled_bdf2_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (
    TerminalPIParameters,
    TerminalVesselGeometry,
    audit_terminal_inventory_control_contract,
    build_terminal_inventory_control_contract,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


SCHEMA = "dd221-core-v3-full-c3c4-structural-migration-v1"
DEFAULT_WORKBOOK = Path(
    "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"
)
DEFAULT_OUTPUT = Path("logs/dd221_core_v3_full_c3c4_structural_migration_20260815.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_positive(specs: dict[str, Any], name: str) -> float:
    value = specs.get(name)
    if value is None or float(value) <= 0.0:
        raise ValueError(f"DD-221 requires positive workbook specification {name!r}")
    return float(value)


def run(workbook: Path = DEFAULT_WORKBOOK) -> dict[str, Any]:
    source_path = (ROOT / workbook).resolve()
    column = build_column_spec_from_case(load_case_from_excel(str(source_path)))
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("DD-221 requires one staged feed")
    stage_count = int(column.n_stages)
    feed_stage = int(feed.stage_1based)
    rectifying_count = feed_stage - 2
    stripping_count = stage_count - feed_stage - 1
    if rectifying_count < 1 or stripping_count < 1:
        raise ValueError("DD-221 feed must have interior stages above and below it")

    components = tuple(str(name) for name in column.components_excel)
    topology = build_column_topology(
        rectifying_volume_count=rectifying_count,
        stripping_volume_count=stripping_count,
    )
    registry = build_provider_governed_registry(
        components,
        provider_identity="dwsim",
        topology=topology,
    )
    registry_audit = audit_provider_governed_registry(registry)
    base = build_dynamic_dae_contract(
        components,
        topology=topology,
        accepted_root_artifact="pending_full_c3c4_core_v3_root.json",
        product_flow_parameters=("D_pending_full_root", "B_pending_full_root"),
    )
    dynamic_audit = audit_dynamic_dae_contract(base)
    specs = dict(column.specs_raw)
    controlled = build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(
            top_diameter_ft=_required_positive(specs, "Top Drum Diameter (ft)"),
            top_tangent_length_ft=_required_positive(specs, "Top Drum Length (ft)"),
            top_head_shape="two_hemispherical",
            bottom_diameter_ft=_required_positive(specs, "Bottom Sump Diameter (ft)"),
            bottom_height_ft=_required_positive(specs, "Bottom Sump Height (ft)"),
        ),
        controllers=TerminalPIParameters(
            top_kc=_required_positive(specs, "Top Level Kc"),
            top_ti_sec=120.0,
            bottom_kc=_required_positive(specs, "Bottom Level Kc"),
            bottom_ti_sec=_required_positive(specs, "Bottom Level Ti (sec)"),
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )
    controlled_audit = audit_terminal_inventory_control_contract(controlled)
    bdf2 = build_controlled_bdf2_contract(controlled)
    bdf2_audit = audit_controlled_bdf2_contract(bdf2)

    source_stages = list(range(1, stage_count + 1))
    expected_volume_count = 1 + rectifying_count + 1 + stripping_count + 1
    expected_registry_count = 2 * stage_count * (len(components) + 1)
    expected_dynamic_count = expected_registry_count - 2
    expected_controlled_count = expected_dynamic_count + 4
    expected_history_count = 2 * (stage_count * len(components) + stage_count + 2)
    gates = {
        "source_is_20_stage_c3c4": stage_count == 20
        and feed_stage == 12
        and components == ("n-Propane", "n-Butane", "n-Pentane"),
        "source_map_is_complete": len(topology.volume_ids)
        == len(source_stages)
        == expected_volume_count
        and source_stages == list(range(1, 21)),
        "registry_passes": registry_audit.pass_gate
        and registry_audit.unknown_count == expected_registry_count,
        "dynamic_dae_passes": dynamic_audit.pass_gate
        and dynamic_audit.solve_variable_count == expected_dynamic_count,
        "terminal_control_passes": controlled_audit.pass_gate
        and controlled_audit.solve_variable_count == expected_controlled_count,
        "controlled_bdf2_passes": bdf2_audit.pass_gate
        and bdf2_audit.solve_variable_count == expected_controlled_count
        and bdf2_audit.history_value_count == expected_history_count,
        "conservation_is_structural": registry_audit.component_conservation_passed
        and registry_audit.energy_conservation_passed
        and dynamic_audit.component_conservation_passed
        and dynamic_audit.energy_conservation_passed,
        "interior_ownership_is_generic": {
            row.physical_owner for row in registry.residuals
        }.issubset(
            {
                *topology.volume_ids,
                "total_condenser_reflux_drum_boundary",
            }
        )
        and not any(
            row.physical_owner.startswith("stage_") for row in registry.residuals
        ),
        "property_free": not registry_audit.live_property_evaluation_attempted
        and not base.property_evaluation_attempted
        and controlled_audit.preparation_only
        and bdf2_audit.preparation_only,
    }
    passed = all(gates.values())
    return {
        "schema_id": SCHEMA,
        "campaign_id": "DD-221",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": (
            "full_c3c4_structural_migration_passed"
            if passed
            else "full_c3c4_structural_migration_failed"
        ),
        "decision": (
            "authorize_full_c3c4_source_mapping_and_live_readiness_contract"
            if passed
            else "stop_full_c3c4_migration"
        ),
        "source": {
            "workbook": str(workbook).replace("\\", "/"),
            "sha256": _sha256(source_path),
            "stage_count": stage_count,
            "feed_stage_1based": feed_stage,
            "component_names": list(components),
            "source_stage_1based": source_stages,
            "seed_is_accepted_root": False,
        },
        "topology": asdict(topology),
        "mapping": {
            "rectifying_volume_count": rectifying_count,
            "stripping_volume_count": stripping_count,
            "volume_to_source_stage_1based": dict(
                zip(topology.volume_ids, source_stages, strict=True)
            ),
        },
        "dimensions": {
            "provider_governed_registry": expected_registry_count,
            "dynamic_dae": expected_dynamic_count,
            "terminal_controlled_dae": expected_controlled_count,
            "controlled_bdf2": expected_controlled_count,
            "bdf2_history_values": expected_history_count,
        },
        "terminal_inputs": {
            "geometry": asdict(controlled.geometry),
            "controllers": asdict(controlled.controllers),
            "top_ti_sec_provenance": (
                "provisional value inherited from accepted reduced Core V3 proof; "
                "numerical tuning is not authorized by DD-221"
            ),
        },
        "audits": {
            "registry": asdict(registry_audit),
            "dynamic_dae": asdict(dynamic_audit),
            "terminal_control": asdict(controlled_audit),
            "controlled_bdf2": asdict(bdf2_audit),
        },
        "gates": gates,
        "pass_gate": passed,
        "execution_prohibitions": {
            "dwsim_started": False,
            "property_call_attempted": False,
            "residual_evaluation_attempted": False,
            "jacobian_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
        },
        "next_gate": (
            "one separately frozen full-source mapping and live residual/Jacobian "
            "readiness audit; the workbook profile is an audit point, not an "
            "accepted dynamic root"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args.workbook)
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
