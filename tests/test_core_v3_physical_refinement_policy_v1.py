import json
from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (
    InventoryRefinementLimits,
    assess_inventory_refinement,
)


LIMITS = InventoryRefinementLimits(
    maximum_absolute_component_difference_lbmol=1.0e-4,
    maximum_state_relative_difference_with_1_lbmol_floor=1.0e-5,
    maximum_volume_holdup_relative_component_difference=1.0e-6,
    component_difference_l1_lbmol=2.0e-4,
    absolute_signed_total_inventory_difference_lbmol=1.0e-9,
)
ROOT = Path(__file__).resolve().parents[1]


def test_trace_component_relative_diagnostic_does_not_veto_physical_pass():
    initial = np.asarray([[100.0, 1.0e-4], [50.0, 50.0]])
    coarse = initial + np.asarray([[1.0e-6, 5.0e-8], [0.0, 0.0]])
    refined = initial + np.asarray([[0.0, 0.0], [1.05e-6, 0.0]])

    result = assess_inventory_refinement(initial, coarse, refined, LIMITS)

    assert result.legacy_unfloored_relative_diagnostic == pytest.approx(5.0e-4)
    assert result.pass_gate
    assert all(result.gates.values())


def test_physical_limit_failure_still_rejects_refinement():
    initial = np.asarray([[100.0, 1.0], [50.0, 50.0]])
    coarse = initial + np.asarray([[2.0e-4, 0.0], [0.0, 0.0]])
    refined = initial

    result = assess_inventory_refinement(initial, coarse, refined, LIMITS)

    assert not result.gates["absolute_component"]
    assert not result.pass_gate


def test_signed_total_gate_detects_uncancelled_inventory_difference():
    initial = np.asarray([[100.0, 100.0]])
    coarse = initial + np.asarray([[8.0e-10, 8.0e-10]])
    refined = initial

    result = assess_inventory_refinement(initial, coarse, refined, LIMITS)

    assert not result.gates["signed_total"]
    assert not result.pass_gate


@pytest.mark.parametrize(
    ("initial", "coarse", "refined", "message"),
    [
        ([[1.0, 2.0]], [[1.0]], [[1.0, 2.0]], "identical shapes"),
        ([[1.0, 0.0]], [[1.0, 2.0]], [[1.0, 2.0]], "finite positive"),
        (
            [[1.0, 2.0]],
            [[1.0, float("nan")]],
            [[1.0, 2.0]],
            "finite positive",
        ),
    ],
)
def test_invalid_inventory_inputs_are_rejected(initial, coarse, refined, message):
    with pytest.raises(ValueError, match=message):
        assess_inventory_refinement(initial, coarse, refined, LIMITS)


def test_limits_must_be_positive():
    with pytest.raises(ValueError, match="finite and positive"):
        InventoryRefinementLimits(
            maximum_absolute_component_difference_lbmol=0.0,
            maximum_state_relative_difference_with_1_lbmol_floor=1.0e-5,
            maximum_volume_holdup_relative_component_difference=1.0e-6,
            component_difference_l1_lbmol=2.0e-4,
            absolute_signed_total_inventory_difference_lbmol=1.0e-9,
        )


def test_dd175_evidence_passes_physical_policy_without_reclassification():
    contract = json.loads(
        (
            ROOT
            / "logs/dd175_core_v3_seven_volume_smaller_moving_step_contract_20260812.json"
        ).read_text(encoding="utf-8")
    )
    result = json.loads(
        (
            ROOT
            / "logs/dd175_core_v3_seven_volume_smaller_moving_step_20260812.json"
        ).read_text(encoding="utf-8")
    )
    limits = InventoryRefinementLimits.from_mapping(
        contract["physical_refinement_limits"]
    )
    assessment = assess_inventory_refinement(
        contract["accepted_root_inventory_lbmol"],
        result["steps"]["full"]["inventory_lbmol"],
        result["steps"]["half2"]["inventory_lbmol"],
        limits,
    )

    assert result["pass_gate"] is False
    assert assessment.pass_gate
    assert assessment.legacy_unfloored_relative_diagnostic == pytest.approx(
        result["refinement"]["relative_inventory_difference"]
    )
    assert assessment.legacy_unfloored_relative_diagnostic > 1.0e-7
