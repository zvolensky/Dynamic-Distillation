import numpy as np
import pytest
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.controlled_terminal_zero_rate_v1 import (
    controlled_terminal_pattern,
    controlled_terminal_variable_names,
    evaluate_controlled_terminal_zero_rate,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    evaluate_zero_rate_readiness,
)
from test_core_v3_zero_rate_readiness_v1 import _zero_fixture


def _evaluate(point):
    provider, spec, reference, state, contract, numerical, _, common = _zero_fixture()
    return evaluate_controlled_terminal_zero_rate(
        contract,
        numerical,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        coordinates=point,
        state_id="dd122_test",
        evaluation_kind="residual",
        **common,
    )


def test_dd122_controlled_terminal_structure_is_square_and_full_rank():
    contract = _zero_fixture()[4]
    pattern = controlled_terminal_pattern(contract)

    assert pattern.shape == (48, 48)
    assert structural_rank(csr_matrix(pattern)) == 48
    assert controlled_terminal_variable_names(contract)[-2:] == (
        "log_D_level_output",
        "log_B_level_output",
    )


def test_dd122_zero_product_coordinates_reproduce_fixed_product_residual():
    provider, spec, reference, state, contract, numerical, point, common = _zero_fixture()
    expected = evaluate_zero_rate_readiness(
        contract,
        numerical,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        coordinates=point,
        state_id="dd122_expected",
        evaluation_kind="residual",
        **common,
    )
    actual = _evaluate(np.concatenate((point, np.zeros(2))))

    assert np.array_equal(actual.scaled, expected.scaled)
    assert actual.distillate_lbmolph == pytest.approx(state.distillate_lbmolph)
    assert actual.bottoms_lbmolph == pytest.approx(state.bottoms_lbmolph)


def test_dd122_product_coordinates_affect_only_owned_boundary_balances():
    contract = _zero_fixture()[4]
    point = np.concatenate((_zero_fixture()[6], np.zeros(2)))
    baseline = _evaluate(point)
    distillate = point.copy()
    distillate[-2] = np.log(1.1)
    changed = _evaluate(distillate)
    changed_rows = set(
        np.asarray(baseline.base.row_names)[
            np.abs(changed.scaled - baseline.scaled) > 1.0e-12
        ]
    )

    assert changed_rows == {
        row
        for row in baseline.base.row_names
        if row.startswith("component_balance[reflux_drum,")
        or row == "energy_balance[reflux_drum]"
    }
    assert np.array_equal(changed.base.terminal_scaled, baseline.base.terminal_scaled)


def test_dd122_rejects_wrong_coordinate_count():
    with pytest.raises(ValueError, match="coordinates are invalid"):
        _evaluate(np.zeros(47))
