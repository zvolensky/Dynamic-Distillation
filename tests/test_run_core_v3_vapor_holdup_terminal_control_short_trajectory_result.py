from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_short_trajectory as dd267


def test_dd267_saved_result_preserves_single_refinement_failure():
    saved = json.loads((dd267.ROOT / dd267.RESULT).read_text(encoding="utf-8"))

    assert not saved["pass_gate"]
    assert [key for key, value in saved["gates"].items() if not value] == [
        "refinement"
    ]
    assert len(saved["nominal_endpoints"]) == 4
    assert len(saved["refined_endpoints"]) == 2
    assert saved["logical_provider_calls"] == 27600
    assert saved["gates"]["new_endpoints"]
    assert saved["gates"]["drum_level_monotonic_toward_setpoint"]
    assert saved["gates"]["sump_level_monotonic_toward_setpoint"]
    assert saved["gates"]["distillate_monotonic"]
    assert saved["gates"]["bottoms_monotonic"]
