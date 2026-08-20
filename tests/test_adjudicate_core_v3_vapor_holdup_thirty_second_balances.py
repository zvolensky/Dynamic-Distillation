from __future__ import annotations

import json

from tools import adjudicate_core_v3_vapor_holdup_thirty_second_balances as dd262


def test_dd262_saved_coordinate_ledger_has_all_120_endpoints():
    assert dd262._saved_coordinates().shape == (120, 258)


def test_dd262_source_ledger_has_recovery_and_39_journals():
    sources = dd262._coordinate_sources()

    assert sources[0] == dd262.dd261.SOURCE_RECOVERY
    assert len(sources) == 40
    assert sources[-1].name == "endpoint_120.json"


def test_dd262_saved_contract_is_read_only_and_preserves_dd261():
    saved = json.loads((dd262.ROOT / dd262.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["authorization"]["preserve_dd261_classification"]
    assert saved["replay"]["endpoint_count"] == 120
    assert saved["replay"]["properties"].startswith("live DWSIM")


def test_dd262_saved_result_accepts_the_scientific_trajectory():
    saved = json.loads((dd262.ROOT / dd262.RESULT).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert all(saved["gates"].values())
    assert saved["decision"] == "accept_dd261_scientific_trajectory_through_thirty_seconds"
    assert saved["component_inventory_identity_max_abs_lbmol"] < 1.0e-11
    assert saved["energy_identity_relative"] < 1.0e-10
    assert saved["endpoint81_reference_parity_max_abs"] == 0.0
    assert saved["final_state_parity_max_abs"] == 0.0
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["state_advance_attempted"]
