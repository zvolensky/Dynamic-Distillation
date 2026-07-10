from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "optimize_column_initialization_residual.py"
_SPEC = spec_from_file_location("optimize_column_initialization_residual", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_selected_stages = _MODULE._selected_stages
_stage_continuity_terms = _MODULE._stage_continuity_terms
_vflow_energy_closure_terms = _MODULE._vflow_energy_closure_terms


def test_selected_stages_supports_generic_interior_selector():
    assert _selected_stages("interior", 5) == [1, 2, 3]
    assert _selected_stages("internal", 5) == [1, 2, 3]


def test_selected_stages_interior_excludes_available_boundaries():
    assert _selected_stages("interior", 2) == []
    assert _selected_stages("interior", 1) == []


def test_stage_continuity_terms_penalizes_selected_region_edges():
    terms = _stage_continuity_terms({1: [0.2], 2: [0.3]}, 5)

    assert terms.tolist() == pytest.approx([0.2, 0.1, -0.3])


def test_vflow_energy_closure_terms_scale_calc_used_mismatch():
    terms = _vflow_energy_closure_terms(
        {
            "vflow_energy_calc_lbmolph": [0.0, 120.0, 80.0],
            "vflow_energy_used_lbmolph": [0.0, 100.0, 100.0],
        },
        [0.0, 100.0, 50.0],
        [1, 2],
        denom_floor_lbmol=1.0,
    )

    assert terms.tolist() == pytest.approx([20.0 / 201.0, -20.0 / 151.0])
