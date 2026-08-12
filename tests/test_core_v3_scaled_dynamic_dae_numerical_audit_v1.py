import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    audit_leading_jacobian,
    dynamic_algebraic_coordinates,
    evaluate_dynamic_implicit_residual,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from test_core_v3_scaled_topology_v1 import _ScaledAnalyticProvider


COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def _fixture():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    geometry = HydraulicGeometry(50.0, 2.0, 3.0, 10.0)
    spec = OperatingSpec(
        component_names=COMPONENTS,
        pressure_psia=np.linspace(200.0, 212.0, 7),
        reflux_lbmolph=6000.0,
        feed_component_lbmolph=np.asarray([2500.0, 4000.0, 800.0]),
        feed_enthalpy_BTUph=9.0e7,
        reboiler_duty_BTUph=5.5e7,
        terminal_liquid_targets_lbmol=np.asarray([1400.0, 800.0]),
        hydraulic_geometry=(geometry,) * 5,
        topology=topology,
    )
    liquid_x = np.asarray(
        [
            [0.90, 0.099, 0.001],
            [0.72, 0.275, 0.005],
            [0.55, 0.43, 0.02],
            [0.35, 0.58, 0.07],
            [0.25, 0.66, 0.09],
            [0.15, 0.73, 0.12],
            [0.05, 0.78, 0.17],
        ]
    )
    reference = NumericalReference(
        liquid_moles_lbmol=np.asarray(
            [1400.0, 50.0, 52.0, 55.0, 58.0, 60.0, 800.0]
        ),
        liquid_mole_fraction=liquid_x,
        temperature_F=np.linspace(135.0, 220.0, 7),
        vapor_mole_fraction=liquid_x[1:].copy(),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            [6000.0, 6100.0, 12000.0, 12200.0, 12500.0]
        ),
        vapor_flow_lbmolph=np.asarray(
            [7700.0, 7600.0, 7500.0, 7800.0, 7950.0, 8100.0]
        ),
        distillate_lbmolph=2400.0,
        bottoms_lbmolph=4900.0,
        bubble_vapor_mole_fraction=np.asarray([0.97, 0.029, 0.001]),
        condenser_duty_reference_BTUph=-5.2e7,
        condenser_duty_scale_BTUph=9.0e7,
    )
    state = PhysicalState(
        liquid_moles_lbmol=reference.liquid_moles_lbmol,
        liquid_mole_fraction=reference.liquid_mole_fraction,
        temperature_F=reference.temperature_F,
        vapor_mole_fraction=reference.vapor_mole_fraction,
        hydraulic_liquid_flow_lbmolph=(
            reference.hydraulic_liquid_flow_lbmolph
        ),
        vapor_flow_lbmolph=reference.vapor_flow_lbmolph,
        distillate_lbmolph=reference.distillate_lbmolph,
        bottoms_lbmolph=reference.bottoms_lbmolph,
        bubble_vapor_mole_fraction=reference.bubble_vapor_mole_fraction,
        condenser_duty_BTUph=reference.condenser_duty_reference_BTUph,
    )
    contract = build_dynamic_dae_contract(
        COMPONENTS,
        topology=topology,
        accepted_root_artifact="accepted.json",
        product_flow_parameters=("D_root", "B_root"),
    )
    return _ScaledAnalyticProvider(), spec, reference, state, contract


def test_dd171_scaled_zero_rate_mapping_uses_seven_volume_shapes():
    provider, spec, reference, state, contract = _fixture()
    evaluation = evaluate_dynamic_implicit_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory_from_state(state),
        rate_coordinates=np.zeros(21),
        algebraic_coordinates=dynamic_algebraic_coordinates(
            spec, reference, state
        ),
        storage_gradient_BTU_lbmol=np.full((7, 3), 100.0),
        fixed_steady_scales=np.ones(56),
        state_id="scaled_dynamic",
        evaluation_kind="residual",
    )

    assert evaluation.raw.shape == evaluation.scaled.shape == (54,)
    assert evaluation.component_rate_lbmolph.shape == (7, 3)
    assert evaluation.energy_storage_rate_BTUph.shape == (7,)
    assert np.allclose(evaluation.component_rate_lbmolph, 0.0)
    assert np.allclose(evaluation.energy_storage_rate_BTUph, 0.0)


def test_dd171_scaled_leading_jacobian_matches_generated_contract():
    provider, spec, reference, state, contract = _fixture()
    audit = audit_leading_jacobian(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory_from_state(state),
        root_algebraic_coordinates=dynamic_algebraic_coordinates(
            spec, reference, state
        ),
        storage_gradient_BTU_lbmol=np.full((7, 3), 100.0),
        fixed_steady_scales=np.ones(56),
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        state_id="scaled_leading",
    )

    assert audit.matrix.shape == (54, 54)
    assert audit.rank == 54
    assert np.isfinite(audit.condition)
    assert audit.zero_rows == ()
    assert audit.zero_columns == ()
    assert audit.unexpected_couplings == ()
