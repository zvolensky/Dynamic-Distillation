#!/usr/bin/env python
"""Audit whether saved DD-223 evidence can localize its conditioning failure."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RESULT = Path("logs/dd223_core_v3_full_c3c4_steady_root_20260815.json")
SOURCE_CONTRACT = Path("logs/dd223_core_v3_full_c3c4_steady_root_contract_20260815.json")
OUTPUT = Path("logs/dd224_core_v3_dd223_diagnostic_evidence_20260815.json")
SCHEMA = "dd224-core-v3-dd223-diagnostic-evidence-v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def run(
    result: Mapping[str, Any] | None = None,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = _load(SOURCE_RESULT) if result is None else dict(result)
    contract = _load(SOURCE_CONTRACT) if contract is None else dict(contract)
    starts: dict[str, Any] = {}
    for name, start in result["starts"].items():
        jacobians = start.get("jacobians", [])
        starts[name] = {
            "final_coordinates_saved": "final_coordinates" in start,
            "physical_state_saved": "state" in start,
            "block_norms_saved": "final_block_norms" in start,
            "complete_residual_vector_saved": any(
                key in start for key in ("final_raw_residual", "final_scaled_residual")
            ),
            "jacobian_spectra_saved": bool(jacobians)
            and all("singular_values" in item for item in jacobians),
            "complete_jacobian_matrices_saved": bool(jacobians)
            and all("matrix" in item for item in jacobians),
        }
    coordinate_ledger_available = bool(
        contract.get("source_contract")
        and (ROOT / contract["source_contract"]).exists()
    )
    endpoint_replay_possible = all(
        item["final_coordinates_saved"] and item["physical_state_saved"]
        for item in starts.values()
    ) and coordinate_ledger_available
    localization_possible = all(
        item["complete_residual_vector_saved"]
        and item["complete_jacobian_matrices_saved"]
        for item in starts.values()
    )
    return {
        "schema_id": SCHEMA,
        "campaign_id": "DD-224",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": (
            "dd223_evidence_complete_for_static_localization"
            if localization_possible
            else "dd223_evidence_incomplete_for_static_localization"
        ),
        "decision": (
            "perform_zero_call_static_conditioning_analysis"
            if localization_possible
            else "authorize_one_frozen_read_only_endpoint_replay_contract"
        ),
        "source_classification_preserved": result["classification"],
        "source_decision_preserved": result["decision"],
        "starts": starts,
        "coordinate_ledger_available": coordinate_ledger_available,
        "static_localization_possible": localization_possible,
        "read_only_endpoint_replay_possible": endpoint_replay_possible,
        "missing_evidence": [
            "complete per-row raw and scaled endpoint residual vectors",
            "complete endpoint Jacobian matrices at both frozen finite-difference steps",
        ] if not localization_possible else [],
        "required_replay_scope": {
            "endpoints": list(result["starts"]),
            "coordinates": len(contract["lower_bounds"]),
            "jacobian_steps": contract["settings"]["endpoint_jacobian_steps"],
            "jacobian_mode": contract["settings"]["jacobian_mode"],
            "nonlinear_solve": False,
            "state_advance": False,
            "timestep": False,
            "dynamic_integration": False,
        },
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "timestep_calls": 0,
        "dynamic_integration_calls": 0,
        "pass_gate": (not localization_possible) and endpoint_replay_possible,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = run()
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
