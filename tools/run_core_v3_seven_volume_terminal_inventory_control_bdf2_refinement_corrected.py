#!/usr/bin/env python
"""Prepare or execute DD-200 after DD-199's history-adapter correction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement as dd199  # noqa: E402


SCHEMA = "dd200-core-v3-seven-volume-controlled-bdf2-refinement-contract-v1"
RESULT_SCHEMA = "dd200-core-v3-seven-volume-controlled-bdf2-refinement-result-v1"
DD199_RESULT = Path("logs/dd199_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_20260813.json")
CONTRACT = Path("logs/dd200_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_contract_20260813.json")
RESULT = Path("logs/dd200_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_20260813")
CONTRACT_DOC = Path("docs/dd_200_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_contract_20260813.md")
RESULT_DOC = Path("docs/dd_200_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_20260813.md")
IMPLEMENTATION = (
    *dd199.IMPLEMENTATION,
    "tools/run_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_corrected.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_trajectory_v1.py",
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
        output = dd199.prepare(
            dd199.DD187_CONTRACT,
            dd199.DD198_RESULT,
            dd199.DD188_RESULT,
            args.contract,
            args.contract_doc,
            campaign_id="DD-200",
            schema_id=SCHEMA,
            result_schema_id=RESULT_SCHEMA,
            additional_sources=(DD199_RESULT,),
            implementation_paths=IMPLEMENTATION,
        )
        print(json.dumps({
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "paths": output["paths"],
            "campaign_executed": output["campaign_executed"],
        }, indent=2))
    else:
        output = dd199.execute(args.contract, args.result, args.result_doc)
        print(json.dumps({
            "classification": output["classification"],
            "pass_gate": output["pass_gate"],
            "decision": output["decision"],
        }, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
