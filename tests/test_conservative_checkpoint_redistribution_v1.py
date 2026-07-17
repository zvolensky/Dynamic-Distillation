import numpy as np
import pytest

from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    ConservativeNodeTarget,
    solve_energy_only_pressure_ordering,
    weighted_isotonic_nondecreasing,
)
from dynamic_distillation.uv_flash_stage_v1 import (
    BTU_PER_PSI_FT3,
    R_GAS_PSIA_FT3_PER_LBMOL_R,
)


class _FakeUvProvider:
    def __init__(self):
        self.x = np.asarray([0.5, 0.5], dtype=float)
        self.y = np.asarray([0.25, 0.75], dtype=float)
        self.rhoL = 8.0

    def _hL(self, T_F, P_psia):
        return 12.0 + 0.8 * float(T_F) + 0.05 * float(P_psia)

    def _hV(self, T_F, P_psia):
        return 30.0 + 1.1 * float(T_F) + 0.02 * float(P_psia)

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        return (
            self.x.tolist(),
            self.y.tolist(),
            (self.y / self.x).tolist(),
            self._hL(T_F, P_psia),
            self._hV(T_F, P_psia),
        )

    def liquid_density_lbmol_ft3(self, T_F, P_psia, x):
        return self.rhoL

    def vapor_z_factor_F_psia(self, T_F, P_psia, y):
        return 1.0


def _target(provider, node_id, position, total_moles, T_F, P_psia, beta):
    z = (1.0 - beta) * provider.x + beta * provider.y
    vL = 1.0 / provider.rhoL
    vV = R_GAS_PSIA_FT3_PER_LBMOL_R * (T_F + 459.67) / P_psia
    uL = provider._hL(T_F, P_psia) - P_psia * vL * BTU_PER_PSI_FT3
    uV = provider._hV(T_F, P_psia) - P_psia * vV * BTU_PER_PSI_FT3
    return ConservativeNodeTarget(
        node_id=node_id,
        position_1based=position,
        total_component_inventory_lbmol=total_moles * z,
        total_internal_energy_BTU=total_moles * ((1.0 - beta) * uL + beta * uV),
        fixed_total_volume_ft3=total_moles * ((1.0 - beta) * vL + beta * vV),
        initial_temperature_F=T_F,
        initial_pressure_psia=P_psia,
        initial_beta_vapor=beta,
    )


def test_weighted_isotonic_projection_enforces_increment_and_preserves_ordered_values():
    projected = weighted_isotonic_nondecreasing(
        [200.0, 220.0, 180.0, 210.0],
        weights=[1.0, 2.0, 1.0, 1.0],
        minimum_increment=0.5,
    )
    assert np.all(np.diff(projected) >= 0.5 - 1.0e-12)
    already_ordered = weighted_isotonic_nondecreasing(
        [100.0, 101.0, 102.0],
        minimum_increment=0.5,
    )
    assert np.allclose(already_ordered, [100.0, 101.0, 102.0])


def test_energy_only_redistribution_preserves_global_energy_and_orders_pressure():
    provider = _FakeUvProvider()
    targets = (
        _target(provider, "top", 1, 10.0, 100.0, 220.0, 0.4),
        _target(provider, "middle", 2, 12.0, 130.0, 180.0, 0.4),
        _target(provider, "bottom", 3, 15.0, 160.0, 200.0, 0.4),
    )
    result = solve_energy_only_pressure_ordering(
        provider=provider,
        targets=targets,
        minimum_pressure_increment_psi=0.01,
    )
    assert result.pressure_energy_feasibility_pass is True
    assert result.root_converged is True
    assert np.all(np.diff(result.final_pressure_psia) >= 0.01 - 1.0e-8)
    assert result.component_conservation_abs_max_lbmol == 0.0
    assert result.total_internal_energy_relative_error < 1.0e-8
    assert result.energy_moved_BTU > 0.0
    assert result.maximum_pressure_change_psi > 0.0
    assert result.maximum_temperature_change_F > 0.0
    assert all(row.converged for row in result.nodes)
    assert result.classification == "energy_only_pressure_ordering_feasible"


def test_isotonic_projection_rejects_nonpositive_weight():
    with pytest.raises(ValueError, match="positive"):
        weighted_isotonic_nondecreasing([1.0, 2.0], weights=[1.0, 0.0])
