from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import probe_core_v3_inworker_reset_efficiency as dd155


class _Provider:
    def __init__(self):
        self._rhoL_cache = {("rho",): 1.0}
        self._cp_cache = {("cp",): (1.0, 2.0)}
        self._mw_components_cache = object()


def test_clear_python_provider_caches_reports_and_clears_all_caches():
    provider = _Provider()
    before = dd155._clear_python_provider_caches(provider)
    assert before == {"rhoL": 1, "cp": 1, "mw": 1}
    assert provider._rhoL_cache == {}
    assert provider._cp_cache == {}
    assert provider._mw_components_cache is None


def test_stage_summary_uses_median_and_maximum_difference():
    summary = dd155._stage_summary(
        [
            {"wall_sec": 3.0, "matrix_max_abs_difference": 0.0},
            {"wall_sec": 1.0, "matrix_max_abs_difference": 2.0e-12},
        ]
    )
    assert summary["median_wall_sec"] == 2.0
    assert summary["maximum_matrix_difference"] == 2.0e-12


def test_classify_reset_identifies_first_recovering_layer():
    diagnosis = dd155._classify_reset(
        {
            "no_reset": 2.0,
            "python_cache_reset": 1.9,
            "provider_rebuild": 1.8,
            "backend_reinitialize": 1.05,
        },
        fresh_reference_sec=1.0,
        aged_ratio_minimum=1.2,
        recovered_to_fresh_ratio_maximum=1.15,
        speedup_minimum=1.2,
    )
    assert diagnosis["aging_reproduced"] is True
    assert diagnosis["recovery_observed"] is True
    assert diagnosis["first_recovering_intervention"] == "backend_reinitialize"


def test_classify_reset_rejects_unrecovered_timing():
    diagnosis = dd155._classify_reset(
        {
            "no_reset": 2.0,
            "python_cache_reset": 1.9,
            "provider_rebuild": 1.8,
            "backend_reinitialize": 1.5,
        },
        fresh_reference_sec=1.0,
        aged_ratio_minimum=1.2,
        recovered_to_fresh_ratio_maximum=1.15,
        speedup_minimum=1.2,
    )
    assert diagnosis["recovery_observed"] is False
    assert diagnosis["first_recovering_intervention"] is None
