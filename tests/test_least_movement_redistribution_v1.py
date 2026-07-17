import numpy as np

from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    ConservativeNodeTarget,
)
from dynamic_distillation.least_movement_redistribution_v1 import (
    assess_multistart_results,
    build_movement_scales,
    build_energy_only_pressure_profile_start,
    conservative_random_start,
    solve_least_movement_redistribution,
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


def _targets(provider):
    return (
        _target(provider, "top", 1, 10.0, 100.0, 220.0, 0.4),
        _target(provider, "middle", 2, 12.0, 130.0, 180.0, 0.4),
        _target(provider, "bottom", 3, 15.0, 160.0, 200.0, 0.4),
    )


def test_random_start_is_globally_conservative_and_positive():
    provider = _FakeUvProvider()
    targets = _targets(provider)
    scales = build_movement_scales(targets)
    q = conservative_random_start(
        targets=targets,
        scales=scales,
        relative_magnitude=0.05,
        seed=42,
    )
    n_nodes = len(targets)
    n_components = 2
    qn = q[: n_nodes * n_components].reshape((n_nodes, n_components))
    qu = q[n_nodes * n_components :]
    delta_n = scales.component_lbmol * qn
    delta_u = scales.energy_BTU * qu
    n0 = np.vstack([node.total_component_inventory_lbmol for node in targets])
    assert np.allclose(np.sum(delta_n, axis=0), 0.0, atol=1.0e-12)
    assert np.sum(delta_u) == np.sum(delta_u)
    assert abs(float(np.sum(delta_u))) < 1.0e-10
    assert np.all(n0 + delta_n > 0.0)


def test_least_movement_solver_orders_pressure_with_exact_conservation():
    provider = _FakeUvProvider()
    targets = _targets(provider)
    result = solve_least_movement_redistribution(
        provider=provider,
        targets=targets,
        minimum_pressure_increment_psi=0.01,
        maximum_outer_iterations=10,
    )
    assert result.converged is True
    assert result.pressure_ordering_pass is True
    assert result.all_local_closures_pass is True
    assert result.component_conservation_relative_max < 1.0e-10
    assert result.energy_conservation_relative < 1.0e-8
    assert result.active_bound_count == 0
    assert result.objective > 0.0
    assert result.diagnostics.material_move_L1_lbmol >= 0.0
    assert result.diagnostics.energy_move_L1_BTU >= 0.0
    assert result.total_uv_solves > 0


def test_linear_pressure_start_conserves_energy_and_multistart_assessment_agrees():
    provider = _FakeUvProvider()
    targets = _targets(provider)
    scales = build_movement_scales(targets)
    q, rows = build_energy_only_pressure_profile_start(
        provider=provider,
        targets=targets,
        base_pressure_psia=[180.0, 200.0, 220.0],
        scales=scales,
    )
    n_nodes = len(targets)
    q_energy = q[n_nodes * 2 :]
    assert abs(float(np.sum(scales.energy_BTU * q_energy))) < 1.0e-6
    assert np.all(np.diff([row.pressure_psia for row in rows]) > 0.0)

    first = solve_least_movement_redistribution(
        provider=provider,
        targets=targets,
        maximum_outer_iterations=10,
    )
    second = solve_least_movement_redistribution(
        provider=provider,
        targets=targets,
        initial_normalized_movement=q,
        maximum_outer_iterations=10,
    )
    assessment = assess_multistart_results(
        results=(("checkpoint", first), ("linear", second)),
        required_relative_spread=1.0e-3,
    )
    assert assessment.reproducible_minimum_pass is True
    assert assessment.best_start_name in {"checkpoint", "linear"}


def test_max_iteration_result_can_pass_when_stationary_and_physically_closed():
    provider = _FakeUvProvider()
    result = solve_least_movement_redistribution(
        provider=provider,
        targets=_targets(provider),
        maximum_outer_iterations=8,
    )
    assert result.converged is True
    assert result.first_order_optimality_norm < 1.0e-6
    assert result.maximum_pressure_order_violation_psi <= 1.0e-6
