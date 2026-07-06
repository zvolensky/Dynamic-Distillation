from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "initialize_column_model_consistent_seed.py"
_SPEC = spec_from_file_location("initialize_column_model_consistent_seed", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_candidate_sort_key = _MODULE._candidate_sort_key
_choose_best = _MODULE._choose_best


def _candidate(name, *, gate=False, max_rel=1.0, tray_total=1000.0, max_abs=1.0):
    return {
        "name": name,
        "audit_summary": {
            "gate_pass": gate,
            "max_relative_rate_per_s": max_rel,
            "max_abs_tray_total_rate_lbmolph": tray_total,
            "max_abs_rate_per_s": max_abs,
        },
    }


def test_choose_best_defaults_to_worst_relative_rate():
    candidates = [
        _candidate("lower_total", max_rel=0.012, tray_total=100.0),
        _candidate("lower_rate", max_rel=0.010, tray_total=900.0),
    ]

    assert _choose_best(candidates, selection="max-rate")["name"] == "lower_rate"


def test_choose_best_prefers_gate_pass_before_metric():
    candidates = [
        _candidate("failed_low_rate", gate=False, max_rel=0.001, tray_total=10.0),
        _candidate("passed_high_rate", gate=True, max_rel=0.010, tray_total=900.0),
    ]

    assert _choose_best(candidates, selection="max-rate")["name"] == "passed_high_rate"


def test_balanced_score_includes_tray_total_residual():
    lower_rate = _candidate("lower_rate", max_rel=0.010, tray_total=1000.0)
    lower_total = _candidate("lower_total", max_rel=0.012, tray_total=10.0)

    assert _candidate_sort_key(lower_total["audit_summary"], selection="balanced") < _candidate_sort_key(
        lower_rate["audit_summary"],
        selection="balanced",
    )
