from pathlib import Path
import sys

import numpy as np


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence as dd204
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (
    build_controlled_bdf2_history,
)


def test_dd204_bdf2_history_payload_round_trip_is_exact():
    history = build_controlled_bdf2_history(
        step_seconds=0.125,
        current_inventory_lbmol=np.asarray(((1.0, 2.0), (3.0, 4.0))),
        prior_inventory_lbmol=np.asarray(((0.9, 1.9), (2.9, 3.9))),
        current_internal_energy_BTU=(10.0, 20.0),
        prior_internal_energy_BTU=(9.0, 19.0),
        current_controller_memory=(0.1, -0.2),
        prior_controller_memory=(0.0, -0.1),
    )

    restored = dd204._history_from_payload(dd204._history_payload(history))

    assert restored.step_seconds == history.step_seconds
    assert np.array_equal(
        restored.current_inventory_lbmol, history.current_inventory_lbmol
    )
    assert np.array_equal(restored.prior_inventory_lbmol, history.prior_inventory_lbmol)
    assert np.array_equal(
        restored.current_internal_energy_BTU, history.current_internal_energy_BTU
    )
    assert np.array_equal(
        restored.prior_internal_energy_BTU, history.prior_internal_energy_BTU
    )
    assert np.array_equal(
        restored.current_controller_memory, history.current_controller_memory
    )
    assert np.array_equal(
        restored.prior_controller_memory, history.prior_controller_memory
    )


def test_dd204_matrix_comparison_uses_order_and_method_not_run_prefix():
    matrix = np.asarray(((1.0, 2.0), (3.0, 4.0)))
    serial = [
        {
            "method": "bdf2",
            "root_epoch": "dd204_serial:bdf2_2",
            "state_id": "dd204_serial:bdf2_2:jacobian",
            "matrix": matrix,
        }
    ]
    parallel = [
        {
            "method": "bdf2",
            "root_epoch": "dd204_parallel:bdf2_2",
            "state_id": "dd204_parallel:bdf2_2:jacobian",
            "matrix": matrix.copy(),
        }
    ]

    comparison = dd204._matrix_comparison(serial, parallel)

    assert comparison["metadata_equal"]
    assert comparison["maximum_absolute_difference"] == 0.0


def test_dd204_matrix_comparison_rejects_method_or_value_change():
    serial = [
        {
            "method": "backward_euler",
            "root_epoch": "serial",
            "state_id": "serial:jacobian",
            "matrix": np.eye(2),
        }
    ]
    parallel = [
        {
            "method": "bdf2",
            "root_epoch": "parallel",
            "state_id": "parallel:jacobian",
            "matrix": np.asarray(((1.0, 0.0), (0.0, 1.1))),
        }
    ]

    comparison = dd204._matrix_comparison(serial, parallel)

    assert not comparison["metadata_equal"]
    assert np.isclose(comparison["maximum_absolute_difference"], 0.1)


def test_dd204_worker_basis_is_counted_once_per_worker_and_root():
    evidence = [
        {"root_epoch": "startup", "basis_rebuilds": 4},
        {"root_epoch": "startup", "basis_rebuilds": 0},
        {"root_epoch": "bdf2", "basis_rebuilds": 4},
        {"root_epoch": "bdf2", "basis_rebuilds": 0},
        {"root_epoch": "bdf2", "basis_rebuilds": 0},
    ]

    summary = dd204._worker_basis_summary(evidence, 4)

    assert summary["pass"]
    assert summary["root_count"] == 2
    assert summary["rebuilds_by_root"] == {"bdf2": 4, "startup": 4}


def test_dd204_worker_basis_rejects_missing_worker_rebuild():
    summary = dd204._worker_basis_summary(
        [{"root_epoch": "startup", "basis_rebuilds": 3}], 4
    )

    assert not summary["pass"]
