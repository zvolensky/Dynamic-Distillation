import numpy as np

from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    PhysicalState,
    audit_colored_numerical_jacobian,
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    encode_state,
    evaluate_residual,
    residual_rows,
    solve_local_bubble,
    structural_pattern,
)


class _AnalyticProvider:
    def phase_fugacity_coefficients(
        self, phase, temperature_F, pressure_psia, composition
    ):
        if str(phase).lower().startswith("l"):
            base = np.asarray([0.35, -0.35, -1.0], dtype=float)
            return np.exp(base - 0.01 * (float(temperature_F) - 120.0))
        return np.ones(3, dtype=float)

    def phase_enthalpy_BTU_lbmol(
        self, phase, temperature_F, pressure_psia, composition
    ):
        offset = 10000.0 if str(phase).lower().startswith("v") else 0.0
        return 100.0 * float(temperature_F) + offset

    def liquid_density_lbmol_ft3(
        self, temperature_F, pressure_psia, composition
    ):
        return 2.0 + 0.001 * float(temperature_F)


def _fixture():
    components = ("A", "B", "C")
    geometry = HydraulicGeometry(
        active_area_ft2=50.0,
        tray_spacing_ft=2.0,
        weir_height_in=3.0,
        weir_length_ft=10.0,
        hydraulic_c_factor=1.0,
    )
    spec = OperatingSpec(
        component_names=components,
        pressure_psia=np.asarray([200.0, 202.0, 204.0, 206.0, 208.0]),
        reflux_lbmolph=6000.0,
        feed_component_lbmolph=np.asarray([2500.0, 4000.0, 800.0]),
        feed_enthalpy_BTUph=9.0e7,
        reboiler_duty_BTUph=5.5e7,
        terminal_liquid_targets_lbmol=np.asarray([1400.0, 800.0]),
        hydraulic_geometry=(geometry, geometry, geometry),
    )
    liquid_x = np.asarray(
        [
            [0.90, 0.099, 0.001],
            [0.60, 0.39, 0.01],
            [0.35, 0.58, 0.07],
            [0.20, 0.70, 0.10],
            [0.05, 0.78, 0.17],
        ]
    )
    vapor_y = np.asarray(
        [
            [0.75, 0.245, 0.005],
            [0.50, 0.47, 0.03],
            [0.30, 0.64, 0.06],
            [0.10, 0.78, 0.12],
        ]
    )
    reference = NumericalReference(
        liquid_moles_lbmol=np.asarray([1400.0, 50.0, 55.0, 60.0, 800.0]),
        liquid_mole_fraction=liquid_x,
        temperature_F=np.asarray([135.0, 155.0, 180.0, 198.0, 220.0]),
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=np.asarray([6000.0, 12000.0, 12500.0]),
        vapor_flow_lbmolph=np.asarray([7700.0, 7500.0, 7800.0, 8100.0]),
        distillate_lbmolph=2400.0,
        bottoms_lbmolph=4900.0,
        bubble_vapor_mole_fraction=np.asarray([0.97, 0.029, 0.001]),
        condenser_duty_reference_BTUph=-5.2e7,
        condenser_duty_scale_BTUph=9.0e7,
    )
    return _AnalyticProvider(), spec, reference


def test_dd092_coordinate_ledger_is_40_and_signed_duty_roundtrips():
    _provider, spec, reference = _fixture()
    layout = coordinate_layout(spec)
    point = np.zeros(40)
    point[layout.condenser_duty] = 0.1
    state = decode_coordinates(spec, reference, point)

    assert len(layout.names) == 40
    assert state.condenser_duty_BTUph == -4.3e7
    assert np.allclose(encode_state(spec, reference, state), point)


def test_dd092_residual_has_exact_ledger_and_conservation():
    provider, spec, reference = _fixture()
    audit = ProviderCallAudit()
    scales = np.ones(40)
    scales[12:32] = 1.0e8
    scales[32:35] = 1.0e4
    scales[35:37] = 1.0e3
    evaluation = evaluate_residual(
        spec,
        reference,
        provider,
        audit,
        np.zeros(40),
        fixed_scales=scales,
        state_id="analytic",
        evaluation_kind="residual",
    )

    assert evaluation.raw.shape == evaluation.scaled.shape == (40,)
    assert [row.block for row in evaluation.rows].count(
        "full_phase_equilibrium"
    ) == 12
    assert [row.block for row in evaluation.rows].count(
        "component_balance"
    ) == 15
    assert [row.block for row in evaluation.rows].count("energy_balance") == 5
    assert [row.block for row in evaluation.rows].count(
        "condenser_bubble_fugacity"
    ) == 3
    assert evaluation.component_telescoping_relative_error < 1.0e-12
    assert evaluation.energy_telescoping_relative_error < 1.0e-10
    assert audit.report()["pass"]
    assert all(
        row["provider_interface"] != "dwsim.tp_flash"
        for row in audit.report()["grouped_records"]
    )


def test_dd092_pattern_assigns_qc_only_to_drum_energy():
    _provider, spec, _reference = _fixture()
    layout = coordinate_layout(spec)
    pattern = structural_pattern(spec)
    rows = residual_rows(spec)
    q_rows = np.flatnonzero(pattern[:, layout.condenser_duty]).tolist()

    assert q_rows == [
        next(
            index
            for index, row in enumerate(rows)
            if row.name == "energy_balance[reflux_drum]"
        )
    ]


def test_colored_jacobian_matches_uncolored_provider_governed_audit():
    provider, spec, reference = _fixture()
    point = np.zeros(len(coordinate_layout(spec).names))
    scales = np.ones(point.size)
    full = audit_numerical_jacobian(
        spec,
        reference,
        provider,
        ProviderCallAudit(),
        point,
        fixed_scales=scales,
        state_id="full",
        step=1.0e-6,
        coupling_tolerance=1.0e-7,
    )
    colored, groups = audit_colored_numerical_jacobian(
        spec,
        reference,
        provider,
        ProviderCallAudit(),
        point,
        fixed_scales=scales,
        state_id="colored",
        step=1.0e-6,
        coupling_tolerance=1.0e-7,
    )

    assert len(groups) < point.size
    assert np.allclose(colored.matrix, full.matrix, atol=1.0e-7, rtol=1.0e-7)
    assert colored.rank == full.rank
    assert colored.bubble_rank == full.bubble_rank


def test_dd092_local_bubble_solve_uses_only_direct_fugacity():
    provider, _spec, reference = _fixture()
    audit = ProviderCallAudit()
    result = solve_local_bubble(
        provider,
        audit,
        pressure_psia=200.0,
        liquid_x=reference.liquid_mole_fraction[0],
        temperature_guess_F=135.0,
        vapor_guess=reference.bubble_vapor_mole_fraction,
        state_id="analytic_bubble",
        evaluation_kind="preparation",
    )

    assert result.success
    assert result.residual_inf_norm < 1.0e-10
    assert audit.report()["pass"]
    assert {
        row["provider_interface"] for row in audit.report()["grouped_records"]
    } == {"dwsim.direct_imposed_phase_fugacity"}


def test_dd092_perturbed_bubble_can_be_encoded_as_a_complete_state():
    provider, spec, reference = _fixture()
    audit = ProviderCallAudit()
    liquid = reference.liquid_mole_fraction.copy()
    liquid[0] = np.asarray([0.88, 0.118, 0.002])
    bubble = solve_local_bubble(
        provider,
        audit,
        pressure_psia=200.0,
        liquid_x=liquid[0],
        temperature_guess_F=135.0,
        vapor_guess=reference.bubble_vapor_mole_fraction,
        state_id="perturbed_bubble",
        evaluation_kind="preparation",
    )
    state = PhysicalState(
        liquid_moles_lbmol=reference.liquid_moles_lbmol,
        liquid_mole_fraction=liquid,
        temperature_F=np.asarray(
            [bubble.temperature_F, *reference.temperature_F[1:]]
        ),
        vapor_mole_fraction=reference.vapor_mole_fraction,
        hydraulic_liquid_flow_lbmolph=reference.hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=reference.vapor_flow_lbmolph,
        distillate_lbmolph=reference.distillate_lbmolph,
        bottoms_lbmolph=reference.bottoms_lbmolph,
        bubble_vapor_mole_fraction=bubble.vapor_mole_fraction,
        condenser_duty_BTUph=-5.0e7,
    )
    point = encode_state(spec, reference, state)
    decoded = decode_coordinates(spec, reference, point)

    assert point.shape == (40,)
    assert np.allclose(decoded.liquid_mole_fraction, state.liquid_mole_fraction)
    assert np.allclose(
        decoded.bubble_vapor_mole_fraction,
        state.bubble_vapor_mole_fraction,
    )
    assert decoded.condenser_duty_BTUph < 0.0
