from __future__ import annotations

import json

import numpy as np

from tools import run_core_v3_vapor_holdup_thirty_second_resume as dd261


def test_dd261_preserved_recovery_is_complete_endpoint_81():
    recovered = json.loads((dd261.ROOT / dd261.SOURCE_RECOVERY).read_text(encoding="utf-8"))

    assert recovered["status"] == "in_progress"
    assert recovered["completed_endpoint_count"] == 81
    assert recovered["last_time_sec"] == 20.25
    assert len(recovered["endpoint_reports"]) == 81
    assert np.asarray(recovered["endpoint_coordinates"]).shape == (81, 258)
    assert all(item["success"] and item["physical_pass"] for item in recovered["endpoint_reports"])


def test_dd261_recovered_reference_round_trips():
    recovered = json.loads((dd261.ROOT / dd261.SOURCE_RECOVERY).read_text(encoding="utf-8"))
    reference = dd261.dd254._reference_from_payload(recovered["next_reference"])
    round_trip = dd261.dd254._reference_payload(reference)

    assert round_trip == recovered["next_reference"]


def test_dd261_saved_contract_is_a_journaled_continuation_not_a_rerun():
    saved = json.loads((dd261.ROOT / dd261.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["trajectory"]["recovered_endpoint_count"] == 81
    assert saved["trajectory"]["remaining_nominal_steps"] == 39
    assert saved["trajectory"]["final_time_sec"] == 30.0
    assert saved["reporting"]["immutable_unique_endpoint_journal"]
    assert not saved["reporting"]["single_live_recovery_replacement"]


def test_dd261_result_is_complete_and_only_the_aggregate_balance_formula_failed():
    saved = json.loads((dd261.ROOT / dd261.RESULT).read_text(encoding="utf-8"))

    assert not saved["pass_gate"]
    assert len(saved["prior_endpoint_reports"]) == 81
    assert len(saved["continuation_endpoint_reports"]) == 39
    assert len(saved["journal_files"]) == 39
    assert not saved["gates"]["component_identity"]
    assert not saved["gates"]["energy_identity"]
    assert all(
        value
        for name, value in saved["gates"].items()
        if name not in {"component_identity", "energy_identity"}
    )
    assert all(saved["refinement_gates"].values())
    assert all(saved["continuity_gates"].values())
