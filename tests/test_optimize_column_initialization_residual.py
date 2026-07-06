from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "optimize_column_initialization_residual.py"
_SPEC = spec_from_file_location("optimize_column_initialization_residual", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_selected_stages = _MODULE._selected_stages


def test_selected_stages_supports_generic_interior_selector():
    assert _selected_stages("interior", 5) == [1, 2, 3]
    assert _selected_stages("internal", 5) == [1, 2, 3]


def test_selected_stages_interior_excludes_available_boundaries():
    assert _selected_stages("interior", 2) == []
    assert _selected_stages("interior", 1) == []
