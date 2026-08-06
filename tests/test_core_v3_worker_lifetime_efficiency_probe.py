from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import probe_core_v3_worker_lifetime_efficiency as dd153


def _records(ratios, fresh_late_factor=1.1):
    output = []
    for path in ("coarse", "refined"):
        for offset, root in enumerate((1, 2, 3)):
            fresh = 1.0 + offset * (fresh_late_factor - 1.0) / 2.0
            ratio = ratios[len(output)]
            output.append(
                {
                    "path": path,
                    "root_index": root,
                    "fresh_median_wall_sec": fresh,
                    "aged_to_fresh_ratio": ratio,
                }
            )
    return output


def test_classify_confirms_lifetime_when_fresh_state_cost_is_stable():
    classification, diagnosis = dd153._classify(
        _records([1.4, 1.5, 1.6, 1.3, 1.6, 1.8]),
        speed_ratio_threshold=1.25,
        required_checkpoint_count=4,
        physical_state_ratio_limit=1.25,
    )
    assert classification == "persistent_worker_lifetime_slowdown_confirmed"
    assert diagnosis["checkpoints_above_threshold"] == 6
    assert diagnosis["median_aged_to_fresh_ratio"] > 1.25


def test_classify_rejects_lifetime_when_fresh_cost_tracks_physical_state():
    classification, diagnosis = dd153._classify(
        _records([1.4] * 6, fresh_late_factor=1.5),
        speed_ratio_threshold=1.25,
        required_checkpoint_count=4,
        physical_state_ratio_limit=1.25,
    )
    assert classification == "worker_lifetime_not_isolated"
    assert max(diagnosis["fresh_late_to_early_ratio"].values()) > 1.25


def test_saved_state_uses_preceding_trajectory_endpoint():
    matrix = [[1.0, 0.0], [0.0, 1.0]]
    result = {
        "trajectories": {
            "coarse": [
                {
                    "inventory_lbmol": [[1.0]],
                    "top_internal_energy_BTU": 2.0,
                    "lower_internal_energy_BTU": [3.0],
                    "controller_memory": [4.0],
                },
                {},
            ]
        },
        "captured_trajectory_evidence": {
            "dd134:coarse": [
                {"capture": {}},
                {
                    "capture": {
                        "initial_coordinates": [0.1, 0.2],
                        "frozen_jacobian": matrix,
                    }
                },
            ]
        },
        "parallel_jacobian_evidence": [
            {"state_id": "dd134:coarse:step_1", "wall_clock_sec": 0.1},
            {"state_id": "dd134:coarse:step_2", "wall_clock_sec": 0.2},
        ],
    }
    state = dd153._saved_state(result, "coarse", 2)
    assert state["previous_top_u_BTU"] == 2.0
    assert state["previous_controller_memory"] == [4.0]
    assert state["aged_wall_sec"] == 0.2
    assert state["coordinates"].tolist() == [0.1, 0.2]
