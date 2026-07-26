import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.pressure_layer_steady_root_v1 import (
    algebraic_sparsity_pattern,
    audit_algebraic_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_pressure_layer_numerical_v1 import _problem, _scales


def _dry_terminal(numerical):
    first = numerical.link_geometry[0]
    return PressureNumericalSpec(
        reference_pressure_psia=numerical.reference_pressure_psia,
        pressure_coordinate_scale_psia=numerical.pressure_coordinate_scale_psia,
        pressure_residual_scale_psia=numerical.pressure_residual_scale_psia,
        dry_tray_pressure_drop_coefficient=(
            numerical.dry_tray_pressure_drop_coefficient
        ),
        component_mw_lbm_per_lbmol=numerical.component_mw_lbm_per_lbmol,
        link_geometry=(
            PressureLinkGeometry(
                active_area_ft2=first.active_area_ft2,
                tray_area_ft2=first.tray_area_ft2,
                weir_height_in=first.weir_height_in,
                include_liquid_head=False,
            ),
            *numerical.link_geometry[1:],
        ),
        enforce_pressure_order=False,
    )


def test_dd103_algebraic_root_system_is_42_by_27_with_14_colors():
    _provider, _spec, _reference, _state, contract, _numerical, _storage = (
        _problem()
    )
    pattern, names = algebraic_sparsity_pattern(contract)
    groups = greedy_column_groups(pattern)

    assert pattern.shape == (42, 27)
    assert len(names) == 27
    assert np.all(np.any(pattern, axis=0))
    assert len(groups) == 14


def test_dd103_analytic_algebraic_jacobian_has_full_column_rank():
    provider, spec, reference, state, contract, numerical, storage = _problem()
    coordinates = np.concatenate(
        (
            dynamic_algebraic_coordinates(spec, reference, state),
            np.zeros(4),
        )
    )
    audit = audit_algebraic_jacobian(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory_from_state(state),
        coordinates=coordinates,
        storage_gradient_BTU_lbmol=storage,
        fixed_steady_scales=_scales(),
        numerical=_dry_terminal(numerical),
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        state_id="dd103_analytic",
    )

    assert audit.matrix.shape == (42, 27)
    assert audit.rank == 27
    assert np.isfinite(audit.condition)
    assert not audit.zero_columns
    assert not audit.unexpected_couplings
