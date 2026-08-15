import json
from pathlib import Path

import pytest

from dynamic_distillation.core_v3.production_session_timing_policy_v1 import (
    ProductionSegmentTimingLimit,
    ProductionSessionTimingLimits,
    assess_production_session_timing,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_session_v1 import (
    ProductionSessionSegmentEvidence,
    ProductionSessionTiming,
)


ROOT = Path(__file__).resolve().parents[1]
DD215_RESULT = ROOT / "logs" / "dd215_core_v3_bdf2_reusable_session_proof_20260815.json"


def _limits():
    return ProductionSessionTimingLimits(
        segment_limits=(
            ProductionSegmentTimingLimit("dd215_coarse", 20.0),
            ProductionSegmentTimingLimit("dd215_refined", 10.0),
        ),
        maximum_startup_wall_seconds=5.0,
        maximum_active_wall_seconds=25.0,
        maximum_shutdown_wall_seconds=10.0,
        maximum_total_wall_seconds=40.0,
        maximum_unattributed_wall_seconds=0.1,
    )


def _evidence():
    data = json.loads(DD215_RESULT.read_text(encoding="utf-8"))["session"]
    timing = ProductionSessionTiming(**data["timing"])
    segments = tuple(
        ProductionSessionSegmentEvidence(**item) for item in data["segments"]
    )
    return timing, segments


def test_saved_dd215_timing_passes_all_independent_gates():
    timing, segments = _evidence()

    assessment = assess_production_session_timing(timing, segments, _limits())

    assert assessment.pass_gate
    assert all(assessment.gates.values())
    assert assessment.observed_unattributed_wall_seconds == pytest.approx(
        0.0008267999502085146
    )


def test_slow_segment_fails_even_when_total_session_passes():
    timing = ProductionSessionTiming(1.0, 21.0, 1.0, 23.0)
    segments = (
        ProductionSessionSegmentEvidence("dd215_coarse", 20.5, True),
        ProductionSessionSegmentEvidence("dd215_refined", 0.5, True),
    )

    assessment = assess_production_session_timing(timing, segments, _limits())

    assert not assessment.segments_pass
    assert assessment.total_wall_pass
    assert not assessment.pass_gate


def test_complete_session_can_fail_when_all_segments_pass():
    timing = ProductionSessionTiming(4.0, 20.0, 9.0, 41.0)
    segments = (
        ProductionSessionSegmentEvidence("dd215_coarse", 12.0, True),
        ProductionSessionSegmentEvidence("dd215_refined", 8.0, True),
    )

    assessment = assess_production_session_timing(timing, segments, _limits())

    assert assessment.segments_pass
    assert not assessment.total_wall_pass
    assert not assessment.attribution_identity_pass
    assert not assessment.pass_gate


def test_open_session_fails_shutdown_and_total_presence():
    timing = ProductionSessionTiming(1.0, 2.0, None, None)
    segments = (
        ProductionSessionSegmentEvidence("dd215_coarse", 1.0, True),
        ProductionSessionSegmentEvidence("dd215_refined", 1.0, True),
    )

    assessment = assess_production_session_timing(timing, segments, _limits())

    assert not assessment.shutdown_present_pass
    assert not assessment.total_present_pass
    assert not assessment.pass_gate


def test_segment_contract_requires_exact_names_and_order():
    timing, segments = _evidence()

    assessment = assess_production_session_timing(
        timing, tuple(reversed(segments)), _limits()
    )

    assert not assessment.segment_contract_pass
    assert not assessment.pass_gate


def test_active_identity_and_hidden_overhead_are_independent_gates():
    segments = (
        ProductionSessionSegmentEvidence("dd215_coarse", 1.0, True),
        ProductionSessionSegmentEvidence("dd215_refined", 1.0, True),
    )
    bad_active = assess_production_session_timing(
        ProductionSessionTiming(1.0, 2.1, 1.0, 4.0), segments, _limits()
    )
    hidden_overhead = assess_production_session_timing(
        ProductionSessionTiming(1.0, 2.0, 1.0, 4.2), segments, _limits()
    )

    assert not bad_active.active_identity_pass
    assert not hidden_overhead.attribution_identity_pass


def test_limits_reject_ambiguous_or_nonphysical_contracts():
    with pytest.raises(ValueError, match="names must be unique"):
        ProductionSessionTimingLimits(
            segment_limits=(
                ProductionSegmentTimingLimit("same", 1.0),
                ProductionSegmentTimingLimit("same", 2.0),
            ),
            maximum_startup_wall_seconds=1.0,
            maximum_active_wall_seconds=1.0,
            maximum_shutdown_wall_seconds=1.0,
            maximum_total_wall_seconds=1.0,
            maximum_unattributed_wall_seconds=0.0,
        )
    with pytest.raises(ValueError, match="wall limit must be positive"):
        ProductionSegmentTimingLimit("segment", 0.0)
