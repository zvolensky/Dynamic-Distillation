import numpy as np

from dynamic_distillation.dae_index_probe_v1 import (
    _block_svd_metrics,
    _build_probe_blocks,
    _recommend_probe_action,
)


def test_block_svd_metrics_reports_rank_and_condition():
    block = np.asarray([[3.0, 0.0], [0.0, 1.0]], dtype=float)
    out = _block_svd_metrics(block)
    assert np.isclose(out["sigma_max"], 3.0)
    assert np.isclose(out["sigma_min"], 1.0)
    assert np.isclose(out["cond"], 3.0)
    assert np.isclose(out["rank"], 2.0)


def test_build_probe_blocks_matches_expected_partition():
    blocks = _build_probe_blocks(n_active=2, n_total_stages=4)
    assert blocks["stage"].row_slice == slice(0, 6)
    assert blocks["node_energy"].row_slice == slice(6, 8)
    assert blocks["liquid_flow"].row_slice == slice(8, 12)
    assert blocks["vapor_flow"].row_slice == slice(12, 16)
    assert blocks["stage"].col_slice == slice(0, 6)
    assert blocks["node_energy"].col_slice == slice(6, 8)
    assert blocks["liquid_flow"].col_slice == slice(8, 12)
    assert blocks["vapor_flow"].col_slice == slice(12, 16)

    blocks_reg = _build_probe_blocks(n_active=2, n_total_stages=4, include_vapor_regularization=True)
    assert blocks_reg["vapor_regularization"].row_slice == slice(16, 20)
    assert blocks_reg["vapor_regularization"].col_slice == slice(12, 16)


def test_recommend_probe_action_prioritizes_vapor_regularization():
    out = _recommend_probe_action(
        block_metrics={
            "vapor_flow": {"cond": 1.0e7},
        },
        cross_coupling={"vapor_flow_to_stage": 0.1},
        residual_summary={"vapor_scaled_inf": 0.5},
    )
    assert "vapor regularization" in out

    out2 = _recommend_probe_action(
        block_metrics={
            "vapor_flow": {"cond": 100.0},
        },
        cross_coupling={"vapor_flow_to_stage": 0.3},
        residual_summary={"vapor_scaled_inf": 0.5},
    )
    assert "strongly coupled" in out2
