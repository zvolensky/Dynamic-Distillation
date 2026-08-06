# DD-166 Hybrid-Jacobian Memoized Short-Trajectory Result

- Classification: `hybrid_jacobian_memoized_short_trajectory_failed`
- Decision: `retain_parallel_memoized_dwsim_jacobians`
- Completed roots: `30`
- Minimum memo hit fraction: `0.695578`
- Trajectory wall: `10.075 s`
- DD-158 trajectory ratio: `1.887460`
- Pool startup wall: `28.792 s`
- Total governed wall: `47.926 s`
- Projected five-minute wall: `548.640 s`

All 30 roots completed, memo accounting was exact, provider ownership passed,
and the ordinary first-step, refinement, controller-direction, kinematic,
pressure, physicality, and conservation checks remained acceptable. Complete
capture equivalence failed because the stored frozen Jacobians are deliberately
different, while the performance gates failed independently and decisively.
The accepted four-worker memoized DWSIM path remains both faster and simpler.

DWSIM retained every main-process residual, line-search, convergence, and endpoint decision.
