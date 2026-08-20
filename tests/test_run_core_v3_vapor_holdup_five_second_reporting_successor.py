from __future__ import annotations

import json

import numpy as np

from tools import run_core_v3_vapor_holdup_five_second_reporting_successor as dd258
from tools import run_core_v3_vapor_holdup_parallel_trajectory as dd254
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (
    decode_vapor_holdup_endpoint,
)


def test_dd258_reporter_maps_real_tuple_links_and_all_volumes_property_free():
    problem = dd254._disturbed_problem()
    endpoint = decode_vapor_holdup_endpoint(
        problem["contract"], problem["reference"], problem["numerical"], np.zeros(258)
    )

    profile = dd258.stage_profile(problem, endpoint)

    assert len(profile) == 20
    assert [item["volume"] for item in profile] == list(
        problem["contract"].topology.column.volume_ids
    )
    assert sum(item["vapor_flow_out_lbmolph"] is not None for item in profile) == 19
    assert all(len(item["liquid_mole_fractions"]) == 3 for item in profile)
    assert all(len(item["vapor_mole_fractions"]) == 3 for item in profile)


def test_dd258_saved_contract_preserves_dd257_science_and_freezes_reporter():
    saved = json.loads((dd258.ROOT / dd258.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["trajectory"]["duration_sec"] == 5.0
    assert saved["trajectory"]["steps_per_path"] == 20
    assert saved["reporter"]["preflight_requires_all_volumes"] == 20
    assert saved["reporter"]["preflight_requires_all_vapor_links"] == 19


def test_dd258_saved_result_records_serialization_hard_stop():
    saved = json.loads((dd258.ROOT / dd258.RESULT).read_text(encoding="utf-8"))

    assert not saved["pass_gate"]
    assert saved["decision"] == "stop_five_second_extension_work"
    assert saved["failure"]["exception_type"] == "TypeError"
    assert saved["accepted_endpoint_count"] == 0
    assert not saved["state_advance_accepted"]
    assert not saved["retry_attempted"]
    assert not saved["successor_attempted"]
