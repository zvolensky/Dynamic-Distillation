from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_memoized_captured_short_trajectory as dd158


def test_memo_summary_requires_per_root_accounting():
    summary = dd158._memo_summary(
        [
            {"state_id": "a", "thermo_memo_hits": 8, "thermo_memo_misses": 2},
            {"state_id": "b", "thermo_memo_hits": 6, "thermo_memo_misses": 4},
        ]
    )
    assert summary["hits"] == 14
    assert summary["misses"] == 6
    assert summary["calls"] == 20
    assert summary["hit_fraction"] == 0.7
    assert summary["minimum_root_hit_fraction"] == 0.6


def test_memo_summary_rejects_absent_memo_evidence_naturally():
    summary = dd158._memo_summary([{"state_id": "a"}])
    assert summary["calls"] == 0
    assert summary["minimum_root_hit_fraction"] == 0.0
