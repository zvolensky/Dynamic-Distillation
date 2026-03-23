from types import SimpleNamespace

import numpy as np

from dynamic_distillation.uv_flash_sandbox_simultaneous_v1 import (
    SimultaneousMini8Evaluation,
    SimultaneousMini8Layout,
    SimultaneousSolveResult,
    _attempt_preview_step,
    _adapt_simultaneous_dt,
    _adapt_vapor_target_relax,
    _blend_next_seed,
    _blend_flow_target,
    _build_vapor_regularization_chunks,
    _scale_residual_blocks,
    solve_simultaneous_algebraic_state,
)
from dynamic_distillation.uv_flash_sandbox_v1 import _LiquidFlowClosure, _LiquidNodeState, _VaporFlowClosure
from dynamic_distillation.uv_flash_stage_v1 import UvFlashStageResult


def _dummy_node(stage_label: int, node_type: str) -> _LiquidNodeState:
    return _LiquidNodeState(
        stage_label=int(stage_label),
        node_type=str(node_type),
        T_F=100.0,
        P_psia=120.0,
        total_component_holdup_lbmol=np.asarray([1.0], dtype=float),
        total_moles_lbmol=1.0,
        x_liq=np.asarray([1.0], dtype=float),
        hL_BTU_lbmol=1.0,
        u_total_BTU=1.0,
    )


def test_simultaneous_layout_roundtrip_and_clip():
    layout = SimultaneousMini8Layout(n_active=2, n_total_stages=4)
    z = layout.join(
        np.asarray([-500.0, 1100.0], dtype=float),
        np.asarray([-5.0, 2000.0], dtype=float),
        np.asarray([-1.0, 2.0], dtype=float),
        -50.0,
        900.0,
        np.asarray([-1.0, 2.0, np.nan, 4.0], dtype=float),
        np.asarray([-3.0, 4.0, 5.0, np.nan], dtype=float),
    )
    z_clip = layout.clip(z)
    stage_t, stage_p, stage_beta, top_t, bottom_t, liquid, vapor = layout.split(z_clip)
    assert np.all(stage_t >= -200.0)
    assert np.all(stage_t <= 1000.0)
    assert np.all(stage_p >= 1.0)
    assert np.all(stage_beta >= 1.0e-8)
    assert np.all(stage_beta <= 1.0 - 1.0e-8)
    assert 40.0 <= top_t <= 400.0
    assert 40.0 <= bottom_t <= 500.0
    assert np.all(liquid >= 0.0)
    assert np.all(vapor >= 0.0)


def test_solve_simultaneous_algebraic_state_converges_on_mocked_linear_system(monkeypatch):
    target = np.asarray([2.0, 3.0, 4.0, 5.0], dtype=float)

    def _mock_eval(*, provider, spec, y, z, **kwargs):
        z_arr = np.asarray(z, dtype=float).reshape((-1,))
        return SimultaneousMini8Evaluation(
            residual=z_arr - target,
            raw_residual=z_arr - target,
            stage_results=[],
            condenser_state=None,
            reboiler_state=None,
            top_node=_dummy_node(0, "distillate_drum"),
            bottom_node=_dummy_node(5, "bottoms_sump"),
            liquid_flow=_LiquidFlowClosure(
                used_lbmolps=np.zeros(1, dtype=float),
                raw_lbmolph=np.zeros(1, dtype=float),
                h_ow_ft=np.zeros(1, dtype=float),
                clamped_flag=np.zeros(1, dtype=float),
            ),
            vapor_flow=_VaporFlowClosure(
                used_lbmolps=np.zeros(1, dtype=float),
                raw_lbmolps=np.zeros(1, dtype=float),
                dp_psia=np.zeros(1, dtype=float),
                h_ow_ft=np.zeros(1, dtype=float),
                clamped_flag=np.zeros(1, dtype=float),
            ),
            diag={},
        )

    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1.evaluate_simultaneous_algebraic_state",
        _mock_eval,
    )
    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1.SimultaneousMini8Layout",
        lambda n_active, n_total_stages: SimpleNamespace(
            z_size=4,
            clip=lambda z: np.asarray(z, dtype=float).reshape((-1,)),
        ),
    )
    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1._clip_newton_delta",
        lambda delta, z_ref, spec: np.asarray(delta, dtype=float).reshape((-1,)),
    )

    spec = SimpleNamespace(active_stage0=np.asarray([1], dtype=int), n_total_stages=1)
    out = solve_simultaneous_algebraic_state(
        provider=None,
        spec=spec,
        y=np.zeros(1, dtype=float),
        z_seed=np.zeros(4, dtype=float),
        max_iter=3,
        residual_tol=1.0e-10,
    )
    assert out.converged
    assert not out.failed
    assert np.allclose(out.z, target, atol=1.0e-8)


def test_scale_residual_blocks_normalizes_energy_and_flow_terms():
    stage = UvFlashStageResult(
        T_F=100.0,
        P_psia=120.0,
        beta_vapor=0.5,
        x=np.asarray([1.0], dtype=float),
        y=np.asarray([1.0], dtype=float),
        K=np.asarray([1.0], dtype=float),
        HL_BTU_lbmol=100.0,
        HV_BTU_lbmol=160.0,
        uL_BTU_lbmol=90.0,
        uV_BTU_lbmol=150.0,
        vL_ft3_lbmol=0.5,
        vV_ft3_lbmol=5.0,
        Z_vapor=1.0,
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )
    spec = SimpleNamespace(
        L_lbmolps=np.asarray([2.0, 3.0], dtype=float),
        V_lbmolps=np.asarray([0.0, 4.0], dtype=float),
        condenser_to_top_nominal_lbmolps=2.0,
        reboiler_to_bottom_nominal_lbmolps=3.0,
    )
    scaled, diag = _scale_residual_blocks(
        stage_raw=[np.asarray([60.0, 10.0, 0.25], dtype=float)],
        stage_results=[stage],
        spec=spec,
        top_energy_raw=500.0,
        bottom_energy_raw=800.0,
        top_energy_state_BTU=10000.0,
        bottom_energy_state_BTU=20000.0,
        liquid_raw=np.asarray([1.0, 1.5], dtype=float),
        vapor_raw=np.asarray([0.0, 2.0], dtype=float),
    )
    assert np.allclose(scaled[0], np.asarray([1.0, 2.0, 0.25], dtype=float))
    assert np.allclose(scaled[1], np.asarray([0.05, 0.04], dtype=float))
    assert np.allclose(scaled[2], np.asarray([0.5, 0.5], dtype=float))
    assert np.allclose(scaled[3], np.asarray([0.0, 0.5], dtype=float))
    assert np.allclose(diag["simul_stage_u_scale"], np.asarray([60.0], dtype=float))


def test_blend_next_seed_relaxes_flow_more_than_stage():
    spec = SimpleNamespace(
        active_stage0=np.asarray([1, 2], dtype=int),
        n_total_stages=4,
        L_lbmolps=np.asarray([2.0, 3.0, 4.0, 5.0], dtype=float),
        V_lbmolps=np.asarray([0.0, 6.0, 7.0, 8.0], dtype=float),
        condenser_to_top_nominal_lbmolps=2.0,
        reboiler_to_bottom_nominal_lbmolps=5.0,
    )
    layout = SimultaneousMini8Layout(n_active=2, n_total_stages=4)
    z_prev = layout.join(
        np.asarray([100.0, 110.0], dtype=float),
        np.asarray([120.0, 130.0], dtype=float),
        np.asarray([0.2, 0.3], dtype=float),
        90.0,
        200.0,
        np.asarray([2.0, 3.0, 4.0, 5.0], dtype=float),
        np.asarray([0.0, 6.0, 7.0, 8.0], dtype=float),
    )
    z_new = layout.join(
        np.asarray([102.0, 112.0], dtype=float),
        np.asarray([122.0, 132.0], dtype=float),
        np.asarray([0.4, 0.5], dtype=float),
        95.0,
        205.0,
        np.asarray([4.0, 5.0, 6.0, 7.0], dtype=float),
        np.asarray([1.0, 8.0, 9.0, 10.0], dtype=float),
    )
    blended = _blend_next_seed(
        z_prev=z_prev,
        z_new=z_new,
        spec=spec,
        stage_relax=0.5,
        node_temp_relax=0.4,
        flow_relax=0.25,
    )
    stage_t, stage_p, stage_beta, top_t, bottom_t, liquid, vapor = layout.split(blended)
    assert np.allclose(stage_t, np.asarray([101.0, 111.0], dtype=float))
    assert np.allclose(stage_p, np.asarray([121.0, 131.0], dtype=float))
    assert np.allclose(stage_beta, np.asarray([0.3, 0.4], dtype=float))
    assert np.isclose(top_t, 92.0)
    assert np.isclose(bottom_t, 202.0)
    assert np.allclose(liquid, np.asarray([2.5, 3.5, 4.5, 5.5], dtype=float))
    assert np.allclose(vapor, np.asarray([0.25, 6.5, 7.5, 8.5], dtype=float))


def test_blend_flow_target_relaxes_toward_raw():
    out = _blend_flow_target(
        anchor=np.asarray([2.0, 4.0], dtype=float),
        raw=np.asarray([6.0, 10.0], dtype=float),
        relax=0.25,
    )
    assert np.allclose(out, np.asarray([3.0, 5.5], dtype=float))


def test_adapt_vapor_target_relax_backs_off_and_then_opens_up():
    base_eval = SimultaneousMini8Evaluation(
        residual=np.zeros(1, dtype=float),
        raw_residual=np.zeros(1, dtype=float),
        stage_results=[],
        condenser_state=None,
        reboiler_state=None,
        top_node=_dummy_node(0, "distillate_drum"),
        bottom_node=_dummy_node(5, "bottoms_sump"),
        liquid_flow=_LiquidFlowClosure(
            used_lbmolps=np.zeros(1, dtype=float),
            raw_lbmolph=np.zeros(1, dtype=float),
            h_ow_ft=np.zeros(1, dtype=float),
            clamped_flag=np.zeros(1, dtype=float),
        ),
        vapor_flow=_VaporFlowClosure(
            used_lbmolps=np.zeros(1, dtype=float),
            raw_lbmolps=np.zeros(1, dtype=float),
            dp_psia=np.zeros(1, dtype=float),
            h_ow_ft=np.zeros(1, dtype=float),
            clamped_flag=np.zeros(1, dtype=float),
        ),
        diag={
            "simul_vflow_scaled_inf": np.asarray([6.0], dtype=float),
            "simul_stage_scaled_inf": np.asarray([0.5], dtype=float),
        },
    )
    solve_bad = SimultaneousSolveResult(
        z=np.zeros(1, dtype=float),
        evaluation=base_eval,
        converged=False,
        failed=False,
        iterations=1,
        accepted_alpha=0.125,
        relaxed_accept=False,
        vapor_target_relax=0.4,
    )
    backed_off = _adapt_vapor_target_relax(
        current_relax=0.4,
        solve=solve_bad,
        min_relax=0.05,
        max_relax=1.0,
        allow_increase=True,
    )
    assert np.isclose(backed_off, 0.28)

    good_eval = SimultaneousMini8Evaluation(
        residual=np.zeros(1, dtype=float),
        raw_residual=np.zeros(1, dtype=float),
        stage_results=[],
        condenser_state=None,
        reboiler_state=None,
        top_node=_dummy_node(0, "distillate_drum"),
        bottom_node=_dummy_node(5, "bottoms_sump"),
        liquid_flow=base_eval.liquid_flow,
        vapor_flow=base_eval.vapor_flow,
        diag={
            "simul_vflow_scaled_inf": np.asarray([0.8], dtype=float),
            "simul_stage_scaled_inf": np.asarray([0.8], dtype=float),
        },
    )
    solve_good = SimultaneousSolveResult(
        z=np.zeros(1, dtype=float),
        evaluation=good_eval,
        converged=True,
        failed=False,
        iterations=1,
        accepted_alpha=0.5,
        relaxed_accept=False,
        vapor_target_relax=0.28,
    )
    opened = _adapt_vapor_target_relax(
        current_relax=0.28,
        solve=solve_good,
        min_relax=0.05,
        max_relax=1.0,
        allow_increase=True,
    )
    assert np.isclose(opened, 0.336)

    held = _adapt_vapor_target_relax(
        current_relax=0.28,
        solve=solve_good,
        min_relax=0.05,
        max_relax=1.0,
        allow_increase=False,
    )
    assert np.isclose(held, 0.28)


def test_solve_simultaneous_algebraic_state_can_reduce_vapor_relax_in_solve(monkeypatch):
    calls = []

    def _mock_eval(*, provider, spec, y, z, z_anchor=None, liquid_target_relax=1.0, vapor_target_relax=0.25, **kwargs):
        calls.append(float(vapor_target_relax))
        z_norm = float(np.linalg.norm(np.asarray(z, dtype=float).reshape((-1,)), ord=np.inf))
        if vapor_target_relax >= 0.2:
            resid_val = 5.0 if z_norm <= 1.0e-12 else 6.0
        else:
            resid_val = 0.0
        return SimultaneousMini8Evaluation(
            residual=np.asarray([resid_val], dtype=float),
            raw_residual=np.asarray([resid_val], dtype=float),
            stage_results=[],
            condenser_state=None,
            reboiler_state=None,
            top_node=_dummy_node(0, "distillate_drum"),
            bottom_node=_dummy_node(5, "bottoms_sump"),
            liquid_flow=_LiquidFlowClosure(
                used_lbmolps=np.zeros(1, dtype=float),
                raw_lbmolph=np.zeros(1, dtype=float),
                h_ow_ft=np.zeros(1, dtype=float),
                clamped_flag=np.zeros(1, dtype=float),
            ),
            vapor_flow=_VaporFlowClosure(
                used_lbmolps=np.zeros(1, dtype=float),
                raw_lbmolps=np.zeros(1, dtype=float),
                dp_psia=np.zeros(1, dtype=float),
                h_ow_ft=np.zeros(1, dtype=float),
                clamped_flag=np.zeros(1, dtype=float),
            ),
            diag={
                "simul_vflow_scaled_inf": np.asarray([resid_val], dtype=float),
                "simul_stage_scaled_inf": np.asarray([0.1], dtype=float),
            },
        )

    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1.evaluate_simultaneous_algebraic_state",
        _mock_eval,
    )
    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1.SimultaneousMini8Layout",
        lambda n_active, n_total_stages: SimpleNamespace(
            z_size=1,
            clip=lambda z: np.asarray(z, dtype=float).reshape((-1,)),
        ),
    )
    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1.finite_difference_jacobian",
        lambda func, x, rel_step=1.0e-6: np.asarray([[1.0]], dtype=float),
    )
    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1._clip_newton_delta",
        lambda delta, z_ref, spec: np.asarray(delta, dtype=float).reshape((-1,)),
    )

    spec = SimpleNamespace(active_stage0=np.asarray([1], dtype=int), n_total_stages=1)
    out = solve_simultaneous_algebraic_state(
        provider=None,
        spec=spec,
        y=np.zeros(1, dtype=float),
        z_seed=np.zeros(1, dtype=float),
        max_iter=3,
        residual_tol=1.0e-12,
        vapor_target_relax=0.25,
        vapor_target_relax_min=0.05,
    )
    assert out.vapor_target_relax < 0.25
    assert calls[0] == 0.25
    assert any(val < 0.25 for val in calls[1:])


def test_adapt_simultaneous_dt_cuts_and_grows_with_solver_quality():
    eval_bad = SimultaneousMini8Evaluation(
        residual=np.asarray([1.0], dtype=float),
        raw_residual=np.asarray([1.0], dtype=float),
        stage_results=[],
        condenser_state=None,
        reboiler_state=None,
        top_node=_dummy_node(0, "distillate_drum"),
        bottom_node=_dummy_node(5, "bottoms_sump"),
        liquid_flow=_LiquidFlowClosure(
            used_lbmolps=np.zeros(1, dtype=float),
            raw_lbmolph=np.zeros(1, dtype=float),
            h_ow_ft=np.zeros(1, dtype=float),
            clamped_flag=np.zeros(1, dtype=float),
        ),
        vapor_flow=_VaporFlowClosure(
            used_lbmolps=np.zeros(1, dtype=float),
            raw_lbmolps=np.zeros(1, dtype=float),
            dp_psia=np.zeros(1, dtype=float),
            h_ow_ft=np.zeros(1, dtype=float),
            clamped_flag=np.zeros(1, dtype=float),
        ),
        diag={},
    )
    solve_bad = SimultaneousSolveResult(
        z=np.zeros(1, dtype=float),
        evaluation=eval_bad,
        converged=False,
        failed=False,
        iterations=1,
        accepted_alpha=0.125,
        relaxed_accept=True,
        vapor_target_relax=0.1,
    )
    dt_cut, streak_cut = _adapt_simultaneous_dt(
        current_dt=0.2,
        solve=solve_bad,
        dt_min=0.025,
        dt_max=0.2,
        good_step_streak=0,
        grow_streak_required=2,
    )
    assert np.isclose(dt_cut, 0.1)
    assert streak_cut == 0

    eval_good = SimultaneousMini8Evaluation(
        residual=np.asarray([1.0e-8], dtype=float),
        raw_residual=np.asarray([1.0e-8], dtype=float),
        stage_results=[],
        condenser_state=None,
        reboiler_state=None,
        top_node=_dummy_node(0, "distillate_drum"),
        bottom_node=_dummy_node(5, "bottoms_sump"),
        liquid_flow=eval_bad.liquid_flow,
        vapor_flow=eval_bad.vapor_flow,
        diag={},
    )
    solve_good = SimultaneousSolveResult(
        z=np.zeros(1, dtype=float),
        evaluation=eval_good,
        converged=True,
        failed=False,
        iterations=1,
        accepted_alpha=0.5,
        relaxed_accept=False,
        vapor_target_relax=0.1,
    )
    dt_hold, streak_hold = _adapt_simultaneous_dt(
        current_dt=0.1,
        solve=solve_good,
        dt_min=0.025,
        dt_max=0.2,
        good_step_streak=1,
        grow_streak_required=2,
    )
    assert np.isclose(dt_hold, 0.12)
    assert streak_hold == 2


def test_build_vapor_regularization_chunks_scales_with_weight():
    spec = SimpleNamespace(
        V_lbmolps=np.asarray([0.0, 4.0, 5.0], dtype=float),
    )
    raw, scaled, diag = _build_vapor_regularization_chunks(
        vapor_trial=np.asarray([0.0, 5.0, 7.0], dtype=float),
        vapor_anchor=np.asarray([0.0, 4.0, 5.0], dtype=float),
        spec=spec,
        weight=4.0,
    )
    assert np.allclose(raw, np.asarray([0.0, 2.0, 4.0], dtype=float))
    assert np.allclose(scaled, np.asarray([0.0, 0.5, 0.8], dtype=float))
    assert np.isclose(diag["simul_vreg_weight"][0], 4.0)
    assert np.isclose(diag["simul_vreg_scaled_inf"][0], 0.8)


def test_attempt_preview_step_backtracks_state_update_before_dt(monkeypatch):
    calls = []
    y_base = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=float)

    def _mock_solve(**kwargs):
        y_trial = np.asarray(kwargs["y"], dtype=float).reshape((-1,))
        calls.append(y_trial.copy())
        bad = bool(np.max(np.abs(y_trial - y_base)) > 0.15)
        eval_out = SimultaneousMini8Evaluation(
            residual=np.asarray([2.0 if bad else 0.0], dtype=float),
            raw_residual=np.asarray([2.0 if bad else 0.0], dtype=float),
            stage_results=[],
            condenser_state=None,
            reboiler_state=None,
            top_node=_dummy_node(0, "distillate_drum"),
            bottom_node=_dummy_node(5, "bottoms_sump"),
            liquid_flow=_LiquidFlowClosure(
                used_lbmolps=np.zeros(1, dtype=float),
                raw_lbmolph=np.zeros(1, dtype=float),
                h_ow_ft=np.zeros(1, dtype=float),
                clamped_flag=np.zeros(1, dtype=float),
            ),
            vapor_flow=_VaporFlowClosure(
                used_lbmolps=np.zeros(1, dtype=float),
                raw_lbmolps=np.zeros(1, dtype=float),
                dp_psia=np.zeros(1, dtype=float),
                h_ow_ft=np.zeros(1, dtype=float),
                clamped_flag=np.zeros(1, dtype=float),
            ),
            diag={},
        )
        return SimultaneousSolveResult(
            z=np.zeros(1, dtype=float),
            evaluation=eval_out,
            converged=not bad,
            failed=False,
            iterations=1,
            accepted_alpha=1.0,
            relaxed_accept=False,
            vapor_target_relax=0.25,
        )

    monkeypatch.setattr(
        "dynamic_distillation.uv_flash_sandbox_simultaneous_v1.solve_simultaneous_algebraic_state",
        _mock_solve,
    )

    spec = SimpleNamespace(
        active_stage0=np.asarray([1], dtype=int),
        component_names=["A"],
        top_node_reference=SimpleNamespace(initial_total_internal_energy_BTU=10.0),
        bottom_node_reference=SimpleNamespace(initial_total_internal_energy_BTU=20.0),
    )
    y = y_base.copy()
    dydt = np.asarray([1.0, 0.0, 1.0, 1.0, 0.0, 0.0], dtype=float)
    accepted, y_trial, preview_solve, dt_used, state_relax = _attempt_preview_step(
        provider=None,
        spec=spec,
        y=y,
        dydt=dydt,
        z_seed=np.zeros(1, dtype=float),
        dt_use=0.2,
        dt_min=0.05,
        max_iter=4,
        residual_tol=1.0e-6,
        jac_rel_step=1.0e-6,
        line_search_max=4,
        liquid_target_relax=1.0,
        vapor_target_relax=0.25,
        vapor_target_relax_min=0.05,
        vapor_regularization_weight=0.0,
    )
    assert accepted
    assert preview_solve is not None
    assert np.isclose(dt_used, 0.2)
    assert np.isclose(state_relax, 0.5)
    assert np.allclose(y_trial, np.asarray([1.1, 2.0, 3.1, 4.1, 5.0, 6.0], dtype=float))
    assert len(calls) >= 2
