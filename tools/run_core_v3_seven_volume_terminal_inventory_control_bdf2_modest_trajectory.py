#!/usr/bin/env python
"""Prepare or execute DD-202's ten-second controlled BDF2 trajectory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement as base  # noqa: E402


SCHEMA = "dd202-core-v3-seven-volume-controlled-bdf2-modest-contract-v1"
RESULT_SCHEMA = "dd202-core-v3-seven-volume-controlled-bdf2-modest-result-v1"
DD190_RESULT = Path("logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_20260813.json")
DD201_RESULT = Path("logs/dd201_core_v3_terminal_inventory_control_bdf2_refinement_response_20260813.json")
CONTRACT = Path("logs/dd202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_contract_20260814.json")
RESULT = Path("logs/dd202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_20260814")
CONTRACT_DOC = Path("docs/dd_202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_contract_20260814.md")
RESULT_DOC = Path("docs/dd_202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_20260814.md")
IMPLEMENTATION = (
    *base.IMPLEMENTATION,
    "tools/run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory.py",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        authorization = base._load(DD201_RESULT)
        if not authorization["pass_gate"]:
            raise RuntimeError("DD-202 requires accepted DD-201")
        output = base.prepare(
            base.DD187_CONTRACT,
            base.DD198_RESULT,
            DD190_RESULT,
            args.contract,
            args.contract_doc,
            campaign_id="DD-202",
            schema_id=SCHEMA,
            result_schema_id=RESULT_SCHEMA,
            additional_sources=(DD201_RESULT,),
            implementation_paths=IMPLEMENTATION,
            duration_seconds=10.0,
            coarse_step_seconds=0.25,
            refined_step_seconds=0.125,
            accuracy_baseline_label="DD-190 backward Euler",
            accuracy_ratio=0.8,
            limits_overrides={"provider_calls": 600000, "wall_clock_sec": 360.0},
            signed_total_policy="response_scaled_external_flow",
            pass_decision="authorize_controlled_bdf2_integration_milestone",
            fail_decision="stop_modest_bdf2_trajectory_path",
        )
        print(json.dumps({"schema_id": output["schema_id"], "contract_payload_sha256": output["contract_payload_sha256"], "paths": output["paths"], "campaign_executed": output["campaign_executed"]}, indent=2))
    else:
        output = base.execute(args.contract, args.result, args.result_doc)
        print(json.dumps({"classification": output["classification"], "pass_gate": output["pass_gate"], "decision": output["decision"]}, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
