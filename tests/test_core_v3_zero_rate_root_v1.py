import numpy as np
import pytest

from dynamic_distillation.core_v3.zero_rate_root_v1 import (
    ZeroRateRootSettings,
    solve_zero_rate_root,
)


def test_dd120_overdetermined_colored_root_converges_exactly():
    matrix = np.asarray(((1.0, 0.0), (0.0, 1.0), (1.0, 1.0)))
    target = np.asarray((1.0, 2.0, 3.0))
    pattern = matrix != 0.0

    outcome = solve_zero_rate_root(
        lambda point, _state_id: matrix @ point - target,
        (0.2, 0.3),
        lower_bounds=(-5.0, -5.0),
        upper_bounds=(5.0, 5.0),
        pattern=pattern,
        settings=ZeroRateRootSettings(),
        state_id="dd120_test",
    )

    assert outcome.success
    assert np.allclose(outcome.final_coordinates, (1.0, 2.0), atol=1.0e-12)
    assert np.max(np.abs(outcome.final_residual)) < 1.0e-12
    assert outcome.jacobian_evaluations > 0


def test_dd120_rejects_non_trf_solver_and_boundary_start():
    objective = lambda point, _state_id: point
    with pytest.raises(ValueError, match="permits only"):
        solve_zero_rate_root(
            objective,
            (0.0,),
            lower_bounds=(-1.0,),
            upper_bounds=(1.0,),
            pattern=((True,),),
            settings=ZeroRateRootSettings(method="dogbox"),
            state_id="dd120_test",
        )
    with pytest.raises(ValueError, match="inputs are invalid"):
        solve_zero_rate_root(
            objective,
            (-1.0,),
            lower_bounds=(-1.0,),
            upper_bounds=(1.0,),
            pattern=((True,),),
            settings=ZeroRateRootSettings(),
            state_id="dd120_test",
        )
