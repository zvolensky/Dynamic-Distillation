from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_core_v3_terminal_inventory_control_bdf2_parallel_replay as dd205


def test_dd205_json_comparison_accepts_exact_nested_science():
    expected = {
        "steps": [{"index": 1, "values": [1.0, 2.0], "gate": True}],
        "decision": "pass",
    }

    comparison = dd205._json_comparison(expected, expected.copy())

    assert comparison["metadata_equal"]
    assert comparison["maximum_numeric_difference"] == 0.0
    assert comparison["numeric_leaf_count"] == 3


def test_dd205_json_comparison_finds_numeric_change_and_path():
    expected = {"steps": [{"values": [1.0, 2.0]}]}
    actual = {"steps": [{"values": [1.0, 2.25]}]}

    comparison = dd205._json_comparison(expected, actual)

    assert comparison["metadata_equal"]
    assert comparison["maximum_numeric_difference"] == 0.25
    assert comparison["worst_numeric_path"] == "steps[0].values[1]"


def test_dd205_json_comparison_rejects_metadata_or_shape_change():
    comparison = dd205._json_comparison(
        {"method": "bdf2", "values": [1.0, 2.0]},
        {"method": "backward_euler", "values": [1.0]},
    )

    assert not comparison["metadata_equal"]
    assert comparison["metadata_mismatches"] == ["method", "values"]
