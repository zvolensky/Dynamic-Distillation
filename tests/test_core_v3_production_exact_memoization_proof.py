from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import prove_core_v3_production_exact_memoization as dd157


def _record(path, mode, wall, hit_fraction=0.0):
    return {
        "path": path,
        "mode": mode,
        "wall_sec": wall,
        "memo_hit_fraction": hit_fraction,
    }


def test_classify_pairs_requires_both_paths_to_pass():
    result = dd157._classify_pairs(
        [
            _record("coarse", "uncached", 3.0),
            _record("refined", "uncached", 4.0),
            _record("coarse", "memoized", 1.0, 0.7),
            _record("refined", "memoized", 2.0, 0.8),
        ],
        speedup_minimum=1.5,
        hit_fraction_minimum=0.6,
    )
    assert result["all_pairs_pass"] is True


def test_classify_pairs_rejects_one_weak_path():
    result = dd157._classify_pairs(
        [
            _record("coarse", "uncached", 3.0),
            _record("refined", "uncached", 4.0),
            _record("coarse", "memoized", 1.0, 0.7),
            _record("refined", "memoized", 3.5, 0.8),
        ],
        speedup_minimum=1.5,
        hit_fraction_minimum=0.6,
    )
    assert result["all_pairs_pass"] is False
