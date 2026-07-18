import numpy as np

from dynamic_distillation.canonical_checkpoint_repair_v1 import (
    CanonicalSourceInput,
    canonicalize_source_node,
    combine_canonical_sources,
    direct_canonical_target,
)
from dynamic_distillation.terminal_energy_volume_audit_v1 import (
    EnergyVolumeRegionInput,
)
from dynamic_distillation.uv_flash_stage_v1 import (
    BTU_PER_PSI_FT3,
    R_GAS_PSIA_FT3_PER_LBMOL_R,
)


class _FakeProvider:
    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        return (10.0 if phase == "liquid" else 30.0) + 0.2 * T_F

    def liquid_density_lbmol_ft3(self, T_F, P_psia, comp):
        return 8.0

    def vapor_z_factor_F_psia(self, T_F, P_psia, comp):
        return 1.0


def _source(node_id, position, *, fixed_volume=None, stored_u_offset=100.0):
    provider = _FakeProvider()
    temperature = 100.0
    pressure = 200.0
    liquid = np.asarray([4.0, 6.0])
    vapor = np.asarray([1.0, 1.0])
    liquid_volume = float(np.sum(liquid)) / 8.0
    vapor_volume = (
        float(np.sum(vapor))
        * R_GAS_PSIA_FT3_PER_LBMOL_R
        * (temperature + 459.67)
        / pressure
    )
    occupied = liquid_volume + vapor_volume
    h = (
        np.sum(liquid)
        * provider.phase_enthalpy_BTU_lbmol(
            "liquid", temperature, pressure, [0.4, 0.6]
        )
        + np.sum(vapor)
        * provider.phase_enthalpy_BTU_lbmol(
            "vapor", temperature, pressure, [0.5, 0.5]
        )
    )
    canonical_u = h - pressure * occupied * BTU_PER_PSI_FT3
    region = EnergyVolumeRegionInput(
        region_id=node_id,
        category="test",
        source_blocks=(node_id,),
        temperature_F=temperature,
        pressure_psia=pressure,
        liquid_inventory_lbmol=liquid,
        vapor_inventory_lbmol=vapor,
        fixed_total_volume_ft3=(
            occupied if fixed_volume is None else float(fixed_volume)
        ),
        mapped_internal_energy_BTU=canonical_u + stored_u_offset,
        mapped_energy_basis="phase_property_sum",
        stored_enthalpy_BTU=None,
    )
    return provider, CanonicalSourceInput(
        node_id=node_id,
        position_1based=position,
        component_inventory_lbmol=liquid + vapor,
        region=region,
        canonical_fixed_volume_ft3=occupied,
        topology="liquid_only_test",
    )


def test_canonicalization_replaces_stored_u_with_live_phase_sum():
    provider, source = _source("sump", 3)
    mapping = canonicalize_source_node(provider=provider, source=source)
    assert np.isclose(mapping.mapping_energy_change_BTU, -100.0)
    assert mapping.canonical_volume_mismatch_relative < 1.0e-12
    target = direct_canonical_target(mapping=mapping)
    assert (
        target.target.total_internal_energy_BTU
        == mapping.canonical_internal_energy_BTU
    )
    assert target.target.fixed_total_volume_ft3 == mapping.occupied_phase_volume_ft3


def test_combined_canonical_target_preserves_source_components_energy_and_volume():
    provider, first_source = _source("reboiler", 2)
    _, second_source = _source("sump", 2, stored_u_offset=50.0)
    first = canonicalize_source_node(
        provider=provider,
        source=first_source,
    )
    second = canonicalize_source_node(
        provider=provider,
        source=second_source,
    )
    combined = combine_canonical_sources(
        node_id="bottom_terminal",
        position_1based=2,
        sources=(first, second),
        topology="reboiler_plus_liquid_only_sump",
    )
    assert np.allclose(
        combined.target.total_component_inventory_lbmol,
        first.component_inventory_lbmol + second.component_inventory_lbmol,
    )
    assert combined.canonical_internal_energy_BTU == (
        first.canonical_internal_energy_BTU
        + second.canonical_internal_energy_BTU
    )
    assert combined.canonical_fixed_volume_ft3 == (
        first.canonical_fixed_volume_ft3
        + second.canonical_fixed_volume_ft3
    )
    assert np.isclose(combined.mapping_energy_change_BTU, -150.0)
