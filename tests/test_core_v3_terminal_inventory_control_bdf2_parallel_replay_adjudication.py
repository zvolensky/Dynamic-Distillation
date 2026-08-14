from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import adjudicate_core_v3_terminal_inventory_control_bdf2_parallel_replay as dd206


def test_dd206_canonical_hash_treats_tuple_and_list_as_same_json_value():
    assert dd206._canonical_hash({"index": (1, 2)}) == dd206._canonical_hash(
        {"index": [1, 2]}
    )


def test_dd206_representation_mismatch_set_accepts_exact_40_time_pattern():
    suffixes = (
        "maximum_absolute_component_index",
        "maximum_state_relative_index",
        "maximum_volume_relative_index",
    )
    paths = [
        f"shared_time_refinement.comparisons[{index}].physical_metrics.{suffix}"
        for index in range(40)
        for suffix in suffixes
    ]

    assert dd206._expected_representation_mismatches(paths)


def test_dd206_representation_mismatch_set_rejects_missing_path():
    assert not dd206._expected_representation_mismatches(
        [
            "shared_time_refinement.comparisons[0].physical_metrics.maximum_absolute_component_index"
        ]
    )
