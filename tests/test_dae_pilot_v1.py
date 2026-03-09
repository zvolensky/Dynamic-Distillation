"""
test_dae_pilot_v1.py

Unit tests for pilot DAE residual helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dynamic_distillation.dae_pilot_v1 import (
    DaePilotLayout,
    default_algebraic_seed,
    evaluate_pilot_residual,
    finite_difference_jacobian,
)


@dataclass(frozen=True)
class _Col:
    n_stages: int


@dataclass(frozen=True)
class _Inputs:
    P_tray_prev: np.ndarray | None = None
    V_out_prev_lbmolph: np.ndarray | None = None


def test_dae_pilot_layout_split_join_roundtrip():
    layout = DaePilotLayout(n_stages=3)
    z = layout.join(np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0]))
    p, v = layout.split(z)
    assert z.size == 6
    assert np.allclose(p, np.array([1.0, 2.0, 3.0]))
    assert np.allclose(v, np.array([4.0, 5.0, 6.0]))


def test_dae_pilot_layout_split_rejects_bad_size():
    layout = DaePilotLayout(n_stages=2)
    try:
        layout.split(np.array([1.0, 2.0, 3.0]))
    except ValueError as exc:
        assert "Expected z size" in str(exc)
    else:
        raise AssertionError("Expected ValueError for bad z size")


def test_evaluate_pilot_residual_assembles_expected_components():
    col = _Col(n_stages=2)
    inputs = _Inputs()

    called = {"p": None, "v": None}

    def fake_rhs(t_s, y, col_obj, layout_obj, inputs):  # noqa: ANN001
        called["p"] = np.asarray(inputs.P_tray_prev, dtype=float).copy()
        called["v"] = np.asarray(inputs.V_out_prev_lbmolph, dtype=float).copy()
        dydt = np.array([10.0, 20.0], dtype=float)
        diag = {
            "P_psia_hyd": np.array([100.0, 200.0], dtype=float),
            "V_out_lbmolph": np.array([300.0, 400.0], dtype=float),
        }
        return dydt, diag

    y = np.array([1.0, 2.0], dtype=float)
    ydot = np.array([11.0, 19.0], dtype=float)
    z = np.array([101.0, 201.0, 301.0, 399.0], dtype=float)

    res = evaluate_pilot_residual(
        t_s=0.0,
        y=y,
        ydot=ydot,
        z=z,
        col=col,
        layout=None,
        inputs=inputs,
        rhs_func=fake_rhs,
    )

    assert np.allclose(called["p"], np.array([101.0, 201.0]))
    assert np.allclose(called["v"], np.array([301.0, 399.0]))
    assert np.allclose(res.diff, np.array([1.0, -1.0]))
    assert np.allclose(res.alg_pressure, np.array([1.0, 1.0]))
    assert np.allclose(res.alg_vapor, np.array([1.0, -1.0]))
    assert res.full.size == 6


def test_default_algebraic_seed_uses_diag_then_fallback():
    z = default_algebraic_seed(
        n_stages=2,
        diag={
            "P_psia_diag": np.array([np.nan, 205.0], dtype=float),
            "V_out_lbmolph": np.array([np.nan, 520.0], dtype=float),
        },
        p_fallback_psia=np.array([200.0, 210.0], dtype=float),
        v_fallback_lbmolph=np.array([500.0, 530.0], dtype=float),
    )
    assert np.allclose(z, np.array([200.0, 205.0, 500.0, 520.0]))


def test_finite_difference_jacobian_matches_simple_analytic_case():
    def f(x):
        x0 = float(x[0])
        x1 = float(x[1])
        return np.array([x0 * x0 + x1, x0 - x1], dtype=float)

    x = np.array([2.0, -1.0], dtype=float)
    J = finite_difference_jacobian(f, x, rel_step=1.0e-7)
    J_expected = np.array([[4.0, 1.0], [1.0, -1.0]], dtype=float)
    assert np.allclose(J, J_expected, rtol=1e-5, atol=1e-7)

