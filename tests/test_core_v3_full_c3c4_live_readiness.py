from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_full_c3c4_live_readiness as dd222

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    coordinate_layout,
    residual_rows,
    structural_pattern,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


def _mapped_spec():
    workbook = ROOT / dd222.WORKBOOK
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    source = dd222._source_mapping(column)
    return source, dd222._spec(source, feed_enthalpy=1.0)


def test_dd222_maps_every_c3c4_source_stage_to_one_generic_volume():
    source, spec = _mapped_spec()

    assert source["source_stage_1based"] == list(range(1, 21))
    assert source["roles"] == list(spec.topology.volume_ids)
    assert source["roles"][0] == "reflux_drum"
    assert source["roles"][11] == "feed_tray"
    assert source["roles"][-1] == "combined_reboiler_sump"
    assert len(source["hydraulic_geometry"]) == 18
    assert len(source["vapor_flow_reference_lbmolph"]) == 19
    assert source["seed_is_accepted_root"] is False
    assert source["seed_mapping_used_flash_or_column_closure"] is False


def test_dd222_full_live_system_is_160_square_with_15_colors():
    _source, spec = _mapped_spec()
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    pattern = structural_pattern(spec)
    groups = greedy_column_groups(pattern)

    assert len(layout.names) == len(rows) == 160
    assert pattern.shape == (160, 160)
    assert np.all(np.any(pattern, axis=0))
    assert np.all(np.any(pattern, axis=1))
    assert len(groups) == 15


def test_dd222_frozen_budget_is_more_than_six_times_smaller_than_uncolored():
    _source, spec = _mapped_spec()
    layout = coordinate_layout(spec)
    color_count = len(greedy_column_groups(structural_pattern(spec)))
    sentinel_count = len(dd222._sentinel_columns(layout))
    colored = 1 + len(dd222.JACOBIAN_STEPS) * (1 + 2 * color_count) + 2 * sentinel_count
    uncolored = 1 + len(dd222.JACOBIAN_STEPS) * (1 + 2 * len(layout.names))

    assert sentinel_count == 17
    assert colored == 97
    assert uncolored == 643
    assert uncolored / colored > 6.0


def test_dd222_execution_scope_explicitly_excludes_solve_and_dynamics():
    source = (ROOT / "tools/audit_core_v3_full_c3c4_live_readiness.py").read_text(
        encoding="utf-8"
    )

    assert '"nonlinear_solve_attempted": False' in source
    assert '"timestep_attempted": False' in source
    assert '"dynamic_integration_attempted": False' in source
    assert "authorize_one_frozen_full_c3c4_stationary_root_campaign" in source
