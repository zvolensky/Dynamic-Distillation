import numpy as np

from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    ConservativeNodeTarget,
)
from dynamic_distillation.least_movement_redistribution_v1 import (
    MovementScales,
)
from dynamic_distillation.terminal_energy_volume_audit_v1 import (
    EnergyVolumeRegionInput,
    audit_empty_placeholder_invariance,
    audit_energy_scaling,
    audit_energy_volume_region,
)
from dynamic_distillation.uv_flash_stage_v1 import (
    BTU_PER_PSI_FT3,
    R_GAS_PSIA_FT3_PER_LBMOL_R,
)


class _FakeProvider:
    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        base = 10.0 if str(phase) == "liquid" else 30.0
        return base + 0.5 * float(T_F) + 0.01 * float(P_psia)

    def liquid_density_lbmol_ft3(self, T_F, P_psia, comp):
        return 8.0

    def vapor_z_factor_F_psia(self, T_F, P_psia, comp):
        return 1.0


def _region(provider, *, fixed_volume=None, mapped_basis="stored_enthalpy_minus_fixed_pv"):
    temperature = 100.0
    pressure = 200.0
    liquid = np.asarray([4.0, 6.0])
    vapor = np.asarray([1.0, 1.0])
    liquid_total = float(np.sum(liquid))
    vapor_total = float(np.sum(vapor))
    liquid_volume = liquid_total / 8.0
    vapor_molar_volume = (
        R_GAS_PSIA_FT3_PER_LBMOL_R
        * (temperature + 459.67)
        / pressure
    )
    vapor_volume = vapor_total * vapor_molar_volume
    volume = liquid_volume + vapor_volume
    if fixed_volume is not None:
        volume = float(fixed_volume)
    h_liquid = liquid_total * provider.phase_enthalpy_BTU_lbmol(
        "liquid", temperature, pressure, (liquid / liquid_total).tolist()
    )
    h_vapor = vapor_total * provider.phase_enthalpy_BTU_lbmol(
        "vapor", temperature, pressure, (vapor / vapor_total).tolist()
    )
    stored_h = h_liquid + h_vapor
    if mapped_basis == "stored_enthalpy_minus_fixed_pv":
        mapped_u = stored_h - pressure * volume * BTU_PER_PSI_FT3
    else:
        mapped_u = (
            h_liquid
            - pressure * liquid_volume * BTU_PER_PSI_FT3
            + h_vapor
            - pressure * vapor_volume * BTU_PER_PSI_FT3
        )
    return EnergyVolumeRegionInput(
        region_id="control",
        category="interior_control",
        source_blocks=("tray",),
        temperature_F=temperature,
        pressure_psia=pressure,
        liquid_inventory_lbmol=liquid,
        vapor_inventory_lbmol=vapor,
        fixed_total_volume_ft3=volume,
        mapped_internal_energy_BTU=mapped_u,
        mapped_energy_basis=mapped_basis,
        stored_enthalpy_BTU=stored_h,
    )


def test_round_trip_volume_and_phase_aggregation_pass_for_consistent_region():
    provider = _FakeProvider()
    result = audit_energy_volume_region(
        provider=provider,
        region=_region(provider),
    )
    assert result.enthalpy_round_trip_pass is True
    assert result.stored_enthalpy_basis_pass is True
    assert result.mapped_internal_energy_basis_pass is True
    assert result.volume_reconstruction_pass is True
    assert result.phase_aggregation_pass is True


def test_volume_audit_detects_unfilled_fixed_control_volume():
    provider = _FakeProvider()
    result = audit_energy_volume_region(
        provider=provider,
        region=_region(provider, fixed_volume=1000.0),
    )
    assert result.enthalpy_round_trip_pass is True
    assert result.volume_reconstruction_pass is False
    assert result.volume_reconstruction_relative > 0.9


def test_phase_property_energy_basis_matches_phase_sum():
    provider = _FakeProvider()
    result = audit_energy_volume_region(
        provider=provider,
        region=_region(provider, mapped_basis="phase_property_sum"),
    )
    assert result.mapped_internal_energy_basis_pass is True
    assert result.phase_aggregation_pass is True


def test_empty_placeholder_invariance_rejects_hidden_energy():
    good = audit_empty_placeholder_invariance(
        region_id="empty",
        raw_component_inventory_lbmol=[1.0e-14, 0.0],
        raw_stored_enthalpy_BTU=0.0,
        mapped_internal_energy_BTU=0.0,
        mapped_volume_ft3=0.0,
    )
    assert good.pass_gate is True
    bad = audit_empty_placeholder_invariance(
        region_id="empty",
        raw_component_inventory_lbmol=[0.0, 0.0],
        raw_stored_enthalpy_BTU=10.0,
        mapped_internal_energy_BTU=0.0,
        mapped_volume_ft3=0.0,
    )
    assert bad.pass_gate is False


def _target(node_id, energy):
    return ConservativeNodeTarget(
        node_id=node_id,
        position_1based=1,
        total_component_inventory_lbmol=np.asarray([1.0, 1.0]),
        total_internal_energy_BTU=float(energy),
        fixed_total_volume_ft3=1.0,
        initial_temperature_F=100.0,
        initial_pressure_psia=200.0,
        initial_beta_vapor=0.5,
    )


def test_scaling_audit_exposes_cheap_terminal_energy_movement():
    targets = (
        _target("top_terminal", -1.0e7),
        _target("tray_2", -1.0e5),
        _target("tray_3", -1.0e5),
        _target("bottom_terminal", -5.0e6),
    )
    scales = MovementScales(
        component_lbmol=np.ones((4, 2)),
        energy_BTU=np.asarray([1.0e7, 1.0e5, 1.0e5, 5.0e6]),
    )
    result = audit_energy_scaling(
        targets=targets,
        scales=scales,
        neutrality_cost_ratio_limit=10.0,
    )
    assert result.pass_gate is False
    assert result.maximum_to_minimum_cost_ratio == 10000.0
    assert result.terminal_to_interior_cost_ratio_max < 0.001
