from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_thirty_second_trajectory as dd270


def test_dd270_abort_is_preserved_as_a_product_bound_semantics_failure():
    report = json.loads((dd270.ROOT / dd270.RESULT).read_text(encoding="utf-8"))
    journal = dd270.ROOT / dd270.JOURNAL

    assert report["classification"].endswith("aborted_at_product_bound")
    assert report["accepted_new_endpoint_count"] == 6
    assert report["last_accepted_endpoint"]["time_sec"] == 6.5
    assert report["last_accepted_endpoint"]["physical_pass"]
    assert report["abort"]["coordinate_name"] == "bottoms_product_log_ratio"
    assert report["abort"]["next_predictor_value"] > report["abort"]["frozen_upper_bound"]
    assert report["abort"]["other_coordinates_outside_bounds"] == 0
    assert len(list(journal.glob("endpoint_*.json"))) == 6
    assert not report["retry_attempted"]
    assert report["property_calls_after_abort"] == 0
