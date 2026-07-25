import numpy as np

from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    coordinate_layout,
    decode_coordinates,
)
from dynamic_distillation.core_v3.provider_governed_steady_root_v1 import (
    SteadyRootSettings,
    execute_start,
    independent_smooth_start,
    movement_by_family,
    pairwise_root_agreement,
    physical_bounds,
    physical_vector_and_scales,
    prepare_campaign,
)
from test_core_v3_provider_governed_residual_v1 import _fixture


def test_dd093_solver_settings_are_frozen():
    settings = SteadyRootSettings()

    assert settings.method == "trf"
    assert settings.ftol == settings.xtol == settings.gtol == 1.0e-12
    assert settings.max_nfev == 500
    assert settings.x_scale == 1.0
    assert settings.solve_jacobian_step == 1.0e-5
    assert settings.endpoint_jacobian_steps == (1.0e-5, 5.0e-6)
    assert settings.singular_value_relative_stability_tolerance == 0.25


def test_dd093_physical_bounds_cover_every_coordinate_and_signed_duty():
    _provider, spec, reference = _fixture()
    settings = SteadyRootSettings()
    lower, upper = physical_bounds(spec, reference, settings)
    layout = coordinate_layout(spec)

    assert lower.shape == upper.shape == (40,)
    assert np.all(np.isfinite(lower))
    assert np.all(lower < upper)
    duty_lower = (
        reference.condenser_duty_reference_BTUph
        + reference.condenser_duty_scale_BTUph
        * lower[layout.condenser_duty]
    )
    duty_upper = (
        reference.condenser_duty_reference_BTUph
        + reference.condenser_duty_scale_BTUph
        * upper[layout.condenser_duty]
    )
    assert np.isclose(
        duty_lower,
        -3.0 * abs(reference.condenser_duty_reference_BTUph),
    )
    assert np.isclose(
        duty_upper,
        -0.1 * abs(reference.condenser_duty_reference_BTUph),
    )


def test_dd093_independent_start_changes_drum_and_all_five_volumes():
    provider, spec, reference = _fixture()
    audit = ProviderCallAudit()
    point, metadata = independent_smooth_start(
        spec,
        reference,
        provider,
        audit,
    )
    state = decode_coordinates(spec, reference, point)

    assert point.shape == (40,)
    assert not np.allclose(
        state.liquid_mole_fraction[0],
        reference.liquid_mole_fraction[0],
    )
    assert np.all(
        np.max(
            np.abs(
                state.liquid_mole_fraction
                - reference.liquid_mole_fraction
            ),
            axis=1,
        )
        > 0.0
    )
    assert np.all(np.diff(state.temperature_F) > 0.0)
    assert np.all(state.liquid_moles_lbmol > 0.0)
    assert np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
    assert np.all(state.vapor_flow_lbmolph > 0.0)
    assert state.distillate_lbmolph > 0.0
    assert state.bottoms_lbmolph > 0.0
    assert state.condenser_duty_BTUph < 0.0
    assert metadata["bubble_residual_inf_norm"] < 1.0e-10
    assert not metadata["full_residual_used"]
    assert not metadata["partial_root_solve_used"]
    assert not metadata["balance_back_calculation_used"]
    assert not metadata["dd088_root_or_status_used"]
    assert audit.report()["pass"]


def test_dd093_campaign_contains_exactly_three_interior_starts():
    provider, spec, reference = _fixture()
    audit = ProviderCallAudit()
    scales = np.ones(40)
    campaign, metadata = prepare_campaign(
        spec,
        reference,
        provider,
        audit,
        SteadyRootSettings(),
        canonical=np.zeros(40),
        perturbation=np.full(40, 1.0e-4),
        fixed_residual_scales=scales,
    )

    assert tuple(campaign.starts) == (
        "canonical_core_v3_seed",
        "deterministic_dd092_perturbation",
        "independent_smooth_five_volume_seed",
    )
    assert all(point.shape == (40,) for point in campaign.starts.values())
    assert all(
        np.all(point > campaign.lower_bounds)
        and np.all(point < campaign.upper_bounds)
        for point in campaign.starts.values()
    )
    assert campaign.fixed_residual_scales.shape == (40,)
    assert campaign.physical_comparison_scales.shape == (50,)
    assert metadata["condenser_duty_BTUph"] < 0.0


def test_dd093_pairwise_agreement_includes_bubble_and_duty():
    _provider, spec, reference = _fixture()
    canonical = np.zeros(40)
    scales = physical_vector_and_scales(
        spec, reference, canonical
    )[1]
    bubble = canonical.copy()
    bubble[37] = 0.01
    duty = canonical.copy()
    duty[39] = 0.01
    result = pairwise_root_agreement(
        spec,
        reference,
        {"canonical": canonical, "bubble": bubble, "duty": duty},
        scales,
    )

    assert result["canonical__vs__bubble"] > 0.0
    assert result["canonical__vs__duty"] > 0.0


def test_dd094_reporting_handles_scalar_product_and_duty_coordinates():
    _provider, spec, _reference = _fixture()
    layout = coordinate_layout(spec)
    initial = np.zeros(40)
    final = initial.copy()
    final[layout.distillate] = 0.02
    final[layout.bottoms] = -0.03
    final[layout.condenser_duty] = 0.04

    movement = movement_by_family(spec, initial, final)

    assert movement["products"] == 0.03
    assert movement["condenser_duty"] == 0.04


def test_dd094_execute_start_serializes_complete_reporting_path():
    provider, spec, reference = _fixture()
    lower, upper = physical_bounds(spec, reference, SteadyRootSettings())
    scales = np.ones(40)
    scales[12:32] = 1.0e8
    scales[32:35] = 1.0e4
    scales[35:37] = 1.0e3

    result = execute_start(
        spec,
        reference,
        provider,
        name="analytic_reporting_smoke",
        initial=np.zeros(40),
        lower_bounds=lower,
        upper_bounds=upper,
        fixed_scales=scales,
        settings=SteadyRootSettings(max_nfev=1),
    )

    assert result["final_coordinates"].shape == (40,)
    assert set(result["movement_by_coordinate_family"]) == {
        "liquid_moles",
        "liquid_composition",
        "temperature",
        "column_vapor_composition",
        "liquid_flow",
        "vapor_flow",
        "products",
        "bubble_vapor_composition",
        "condenser_duty",
    }
    assert len(result["endpoint_jacobians"]) == 2
    assert result["provider_provenance"]["pass"]
