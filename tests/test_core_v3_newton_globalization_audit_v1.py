from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.newton_globalization_audit_v1 import (
    probe_newton_correction,
)


def _objective(point, _state_id):
    return SimpleNamespace(scaled=np.asarray(point, dtype=float))


def test_fresh_direction_passes_when_stale_direction_fails_armijo():
    common = {
        "objective": _objective,
        "point": [1.0],
        "residual": [1.0],
        "line_search_fractions": [1.0, 0.5, 0.25, 0.125],
        "armijo_fraction": 1.0e-4,
        "name": "fixture",
    }
    stale = probe_newton_correction(jacobian=[[-1.0]], **common)
    fresh = probe_newton_correction(jacobian=[[1.0]], **common)

    assert stale.accepted_fractions == ()
    assert stale.best_residual_inf_norm == 1.125
    assert fresh.accepted_fractions == (1.0, 0.5, 0.25, 0.125)
    assert fresh.best_residual_inf_norm == 0.0


def test_probe_reports_bound_rejection_without_clipping():
    result = probe_newton_correction(
        _objective,
        point=[1.0],
        residual=[1.0],
        jacobian=[[1.0]],
        line_search_fractions=[1.0, 0.5],
        armijo_fraction=1.0e-4,
        lower_bounds=[0.25],
        upper_bounds=[2.0],
        name="bounded",
    )

    assert not result.candidates[0].within_bounds
    assert result.candidates[0].residual_inf_norm is None
    assert result.candidates[1].within_bounds
    assert result.candidates[1].armijo_accepted


def test_probe_stops_before_candidates_for_singular_jacobian():
    result = probe_newton_correction(
        lambda point, _state_id: SimpleNamespace(scaled=np.asarray(point)),
        point=[1.0, 1.0],
        residual=[1.0, 1.0],
        jacobian=[[1.0, 1.0], [1.0, 1.0]],
        line_search_fractions=[1.0],
        armijo_fraction=1.0e-4,
        condition_limit=1.0e8,
        name="singular",
    )

    assert result.jacobian_rank == 1
    assert np.isinf(result.jacobian_condition)
    assert result.correction_inf_norm is None
    assert result.candidates == ()
