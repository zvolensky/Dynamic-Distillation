from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_memoized_captured_longer_trajectory as dd159


def test_memo_summary_tracks_longer_per_root_accounting():
    summary = dd159._memo_summary(
        [
            {"state_id": "a", "thermo_memo_hits": 818, "thermo_memo_misses": 358},
            {"state_id": "b", "thermo_memo_hits": 820, "thermo_memo_misses": 356},
        ]
    )
    assert summary["hits"] == 1638
    assert summary["misses"] == 714
    assert summary["calls"] == 2352
    assert summary["minimum_root_hit_fraction"] == 818 / 1176


def test_memo_summary_rejects_absent_longer_memo_evidence_naturally():
    summary = dd159._memo_summary([{"state_id": "a"}])
    assert summary["calls"] == 0
    assert summary["minimum_root_hit_fraction"] == 0.0
