from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v3.prescribed_pressure_stationary_v1 import (
    PRESSURE_ROW_BLOCKS,
    apply_prescribed_pressure_targets,
    prescribed_pressure_structural_pattern,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (
    evaluate_vapor_holdup_stationary_residual,
)
from test_core_v3_vapor_holdup_stationary_residual_v1 import _stationary_problem


def test_prescribed_pressure_replaces_only_pressure_rows_and_pattern():
    provider, spec, contract, geometry, reference, inputs, numerical = (
        _stationary_problem()
    )
    base = evaluate_vapor_holdup_stationary_residual(
        contract,
        geometry,
        reference,
        inputs,
        spec.hydraulic_geometry,
        numerical,
        provider,
        ProviderCallAudit(),
        np.zeros(len(contract.variables)),
        state_id="prescribed_pressure_test",
        evaluation_kind="residual",
    )
    target = np.asarray(reference.pressure_psia) + np.linspace(
        0.1, 0.5, len(reference.pressure_psia)
    )
    result = apply_prescribed_pressure_targets(
        contract,
        base,
        target,
        residual_scale_psia=2.0,
    )
    pressure_rows = [
        index for index, row in enumerate(contract.rows) if row.block in PRESSURE_ROW_BLOCKS
    ]
    other_rows = [index for index in range(len(contract.rows)) if index not in pressure_rows]

    assert np.allclose(result.pressure_target_residual_psia, reference.pressure_psia - target)
    assert np.allclose(result.raw[pressure_rows], result.pressure_target_residual_psia)
    assert np.allclose(result.scales[pressure_rows], 2.0)
    assert np.array_equal(result.raw[other_rows], base.raw[other_rows])
    assert all(result.row_names[index].startswith("prescribed_pressure[") for index in pressure_rows)

    pattern = prescribed_pressure_structural_pattern(contract)
    variable_names = [variable.name for variable in contract.variables]
    for row_index, volume in zip(pressure_rows, contract.topology.column.volume_ids):
        nonzero = np.flatnonzero(pattern[row_index])
        assert nonzero.tolist() == [variable_names.index(f"P[{volume}]")]
