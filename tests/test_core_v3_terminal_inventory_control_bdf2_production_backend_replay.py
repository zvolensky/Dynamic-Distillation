from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_core_v3_terminal_inventory_control_bdf2_production_backend_replay as dd208


def test_dd208_normalization_treats_tuple_and_list_as_same_saved_value():
    assert dd208._normalized({"index": (1, 2)}) == dd208._normalized({"index": [1, 2]})


def test_dd208_numeric_difference_finds_nested_change():
    first = {"reports": [{"values": [1.0, 2.0]}]}
    second = {"reports": [{"values": [1.0, 2.25]}]}

    assert dd208._maximum_numeric_difference(first, second) == 0.25


def test_dd208_basis_summary_requires_four_rebuilds_per_root():
    passing = dd208._basis_summary(
        [
            {"root_epoch": "startup", "basis_rebuilds": 4},
            {"root_epoch": "startup", "basis_rebuilds": 0},
            {"root_epoch": "bdf2", "basis_rebuilds": 4},
        ]
    )
    failing = dd208._basis_summary([{"root_epoch": "startup", "basis_rebuilds": 3}])

    assert passing["pass"]
    assert passing["root_count"] == 2
    assert not failing["pass"]
