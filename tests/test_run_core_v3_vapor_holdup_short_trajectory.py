from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_short_trajectory as dd250


def test_dd250_saved_contract_is_frozen_and_nonexecuted():
    saved = json.loads((dd250.ROOT / dd250.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["disturbance"]["feed_component_multiplier"] == 1.001
    assert saved["trajectory"]["duration_sec"] == 1.0
    assert saved["trajectory"]["nominal_endpoint_count"] == 4
    assert saved["trajectory"]["refined_endpoint_count"] == 8
    assert saved["solver"]["max_nfev_per_endpoint"] == 20
