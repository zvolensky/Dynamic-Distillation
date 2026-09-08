from types import SimpleNamespace

import numpy as np

from tools import run_core_v3_water_methanol_dual_level_control as dual_level


def _solution(*, success: bool, x: list[float], nfev: int) -> SimpleNamespace:
    return SimpleNamespace(
        success=success,
        status=1 if success else 0,
        message="converged" if success else "maximum function evaluations exceeded",
        nfev=nfev,
        njev=nfev - 1,
        cost=1.0e-12 if success else 1.0e-6,
        optimality=1.0e-10 if success else 1.0e-4,
        x=np.asarray(x, dtype=float),
    )


def test_extended_warm_start_retries_only_an_exhausted_primary_solve():
    calls: list[tuple[np.ndarray, int]] = []

    def solve(point: np.ndarray, max_nfev: int) -> SimpleNamespace:
        calls.append((np.asarray(point, dtype=float).copy(), max_nfev))
        if len(calls) == 1:
            return _solution(success=False, x=[0.25, 0.75], nfev=max_nfev)
        return _solution(success=True, x=[0.5, 0.5], nfev=12)

    solution, attempts = dual_level._solve_with_recovery(
        solve, np.asarray([0.0, 1.0])
    )

    assert solution.success
    assert [limit for _point, limit in calls] == [
        dual_level.MAX_NFEV,
        dual_level.RECOVERY_MAX_NFEV,
    ]
    np.testing.assert_allclose(calls[1][0], [0.25, 0.75])
    assert [attempt["attempt"] for attempt in attempts] == [
        "primary",
        "extended-warm-start",
    ]


def test_successful_primary_solve_does_not_retry():
    calls: list[int] = []

    def solve(point: np.ndarray, max_nfev: int) -> SimpleNamespace:
        calls.append(max_nfev)
        return _solution(success=True, x=point.tolist(), nfev=5)

    solution, attempts = dual_level._solve_with_recovery(
        solve, np.asarray([0.0, 1.0])
    )

    assert solution.success
    assert calls == [dual_level.MAX_NFEV]
    assert len(attempts) == 1
