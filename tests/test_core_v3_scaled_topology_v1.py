from dataclasses import replace

import numpy as np
import pytest

from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    audit_provider_governed_registry,
    build_column_topology,
    build_provider_governed_registry,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    coordinate_layout,
    evaluate_residual,
    residual_rows,
    structural_pattern,
)


COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


class _ScaledAnalyticProvider:
    def phase_fugacity_coefficients(
        self, phase, temperature_F, pressure_psia, composition
    ):
        if str(phase).lower().startswith("l"):
            return np.exp(
                np.asarray([0.35, -0.35, -1.0], dtype=float)
                - 0.01 * (float(temperature_F) - 120.0)
            )
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


def test_dd167_seven_volume_registry_is_square_full_rank_and_conservative():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    registry = build_provider_governed_registry(COMPONENTS, topology=topology)
    audit = audit_provider_governed_registry(registry)

    assert len(topology.volume_ids) == 7
    assert topology.feed_volume == "feed_tray"
    assert len(topology.liquid_links) == len(topology.vapor_links) == 6
    assert audit.unknown_count == audit.residual_count == 56
    assert audit.expected_count == audit.structural_rank == 56
    assert audit.structural_nullity == 0
    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed
    assert audit.pass_gate


def test_dd167_scaled_registry_preserves_provider_ownership_and_no_execution():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    registry = build_provider_governed_registry(COMPONENTS, topology=topology)
    audit = audit_provider_governed_registry(registry)

    assert audit.vapor_unknown_count == 6
    assert audit.francis_liquid_unknown_count == 5
    assert audit.full_fugacity_row_count == 18
    assert audit.condenser_bubble_row_count == 3
    assert not audit.governing_tp_flash_uses
    assert not audit.production_independent_pr_uses
    assert not audit.live_property_evaluation_attempted
    assert not audit.nonlinear_solve_attempted
    assert not audit.dynamic_integration_attempted


def test_scaled_registry_count_is_generic_in_volume_and_component_count():
    topology = build_column_topology(
        rectifying_volume_count=3,
        stripping_volume_count=2,
    )
    components = ("light", "middle", "heavy", "trace")
    audit = audit_provider_governed_registry(
        build_provider_governed_registry(components, topology=topology)
    )
    expected = 2 * len(topology.volume_ids) * (len(components) + 1)

    assert audit.unknown_count == audit.residual_count == expected
    assert audit.structural_rank == expected
    assert audit.pass_gate


def test_scaled_registry_rejects_broken_adjacency():
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    broken = replace(topology, liquid_links=topology.liquid_links[:-1])

    with pytest.raises(ValueError, match="liquid links"):
        build_provider_governed_registry(COMPONENTS, topology=broken)


def test_dd168_seven_volume_live_residual_ledger_is_generic_and_conservative():
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
    dimension = len(coordinate_layout(spec).names)
    evaluation = evaluate_residual(
        spec,
        reference,
        _ScaledAnalyticProvider(),
        ProviderCallAudit(),
        np.zeros(dimension),
        fixed_scales=np.ones(dimension),
        state_id="scaled_analytic",
        evaluation_kind="residual",
    )

    assert dimension == 56
    assert evaluation.raw.shape == evaluation.scaled.shape == (56,)
    assert structural_pattern(spec).shape == (56, 56)
    assert len(residual_rows(spec)) == 56
    assert evaluation.component_telescoping_relative_error < 1.0e-12
    assert evaluation.energy_telescoping_relative_error < 1.0e-10
