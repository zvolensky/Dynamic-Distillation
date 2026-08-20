#!/usr/bin/env python
"""Audit physical C3/C4 geometry for the Core V3 vapor-holdup successor."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dae_contract,
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    audit_vapor_geometry,
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


DEFAULT_WORKBOOK = Path(
    "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"
)
DEFAULT_JSON = Path("logs/dd237_core_v3_c3c4_vapor_geometry_20260820.json")
DEFAULT_DOC = Path("docs/dd_237_core_v3_c3c4_vapor_geometry_20260820.md")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(workbook_path: Path = DEFAULT_WORKBOOK) -> dict[str, Any]:
    workbook = (ROOT / workbook_path).resolve()
    case = load_case_from_excel(str(workbook))
    column = build_column_spec_from_case(case)
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("C3/C4 geometry audit requires one staged feed")
    topology = build_column_topology(
        rectifying_volume_count=int(feed.stage_1based) - 2,
        stripping_volume_count=int(column.n_stages) - int(feed.stage_1based) - 1,
    )
    geometry = build_column_vapor_geometry(column, case.specs, topology)
    geometry_audit = audit_vapor_geometry(geometry, topology)
    capacities = gross_capacity_mapping(geometry)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=capacities,
    )
    contract = build_vapor_holdup_dae_contract(
        tuple(column.components_excel),
        topology=vapor_topology,
    )
    structural = audit_vapor_holdup_dae_contract(contract)
    passed = bool(geometry_audit.pass_gate and structural.pass_gate)
    return {
        "schema_id": "dd237-core-v3-c3c4-vapor-geometry-v1",
        "classification": (
            "c3c4_vapor_geometry_passed"
            if passed
            else "c3c4_vapor_geometry_failed"
        ),
        "workbook": str(workbook),
        "workbook_sha256": _sha256(workbook),
        "component_names": list(column.components_excel),
        "stage_count": int(column.n_stages),
        "feed_stage_1based": int(feed.stage_1based),
        "geometry": [asdict(record) for record in geometry],
        "geometry_audit": asdict(geometry_audit),
        "structural_audit": asdict(structural),
        "capacity_summary_ft3": {
            "minimum": min(capacities.values()),
            "maximum": max(capacities.values()),
            "top_drum": capacities[topology.top_volume],
            "bottom_combined": capacities[topology.bottom_volume],
        },
        "free_volume_definition": (
            "V_free[j]=gross_capacity[j]-sum_k(NL[j,k])/rhoL[j]"
        ),
        "endpoint_free_volume_evaluated": False,
        "reason_endpoint_free_volume_deferred": (
            "requires separately audited live liquid density at the accepted state"
        ),
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_live_vapor_property_and_eos_residual_implementation"
            if passed
            else "stop_vapor_holdup_successor"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    summary = report["capacity_summary_ft3"]
    structural = report["structural_audit"]
    return "\n".join(
        (
            "# DD-237 C3/C4 Vapor-Holdup Geometry",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Stages/feed stage: `{report['stage_count']} / {report['feed_stage_1based']}`",
            f"- Mapped control volumes: `{report['geometry_audit']['volume_count']}`",
            f"- Structural ledger: `{structural['solve_variable_count']} x {structural['row_count']}`",
            f"- Structural rank: `{structural['structural_rank']}`",
            f"- Top drum gross capacity: `{summary['top_drum']:.6f} ft3`",
            f"- Combined bottom gross capacity: `{summary['bottom_combined']:.6f} ft3`",
            f"- Capacity range: `{summary['minimum']:.6f}` to `{summary['maximum']:.6f} ft3`",
            "",
            "Free vapor volume is not fixed at these capacities. At a live state:",
            "",
            "`V_free[j] = gross_capacity[j] - sum_k(N_L[j,k]) / rho_L[j]`",
            "",
            "No property call, endpoint free-volume evaluation, residual, solve, timestep, or trajectory occurred.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report(args.workbook)
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
