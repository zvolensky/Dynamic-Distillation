#!/usr/bin/env python
"""Run DD-167's property-free seven-volume Core V3 structural gate."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    audit_provider_governed_registry,
    build_column_topology,
    build_provider_governed_registry,
)


DEFAULT_OUTPUT = Path(
    "logs/dd167_core_v3_seven_volume_structural_gate_20260806.json"
)
COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def run() -> dict[str, object]:
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    registry = build_provider_governed_registry(
        COMPONENTS,
        provider_identity="dwsim",
        topology=topology,
    )
    audit = audit_provider_governed_registry(registry)
    block_counts = {
        block: sum(row.block == block for row in registry.residuals)
        for block in sorted({row.block for row in registry.residuals})
    }
    payload: dict[str, object] = {
        "schema_id": "dd167-core-v3-seven-volume-structural-gate-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": (
            "seven_volume_structural_gate_passed"
            if audit.pass_gate
            else "seven_volume_structural_gate_failed"
        ),
        "decision": (
            "authorize_one_frozen_live_dwsim_residual_and_jacobian_audit"
            if audit.pass_gate
            else "stop_scaled_core_v3_path"
        ),
        "scope": "structural_only",
        "component_names": list(COMPONENTS),
        "topology": asdict(topology),
        "equation_block_counts": block_counts,
        "audit": asdict(audit),
        "execution_prohibitions": {
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
        },
        "next_gate": (
            "one separately frozen live-DWSIM numerical residual and Jacobian audit; "
            "no root solve or dynamics"
        ),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run()
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["audit"]["pass_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
