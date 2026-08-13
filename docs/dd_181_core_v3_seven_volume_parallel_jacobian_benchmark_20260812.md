# DD-181 Seven-Volume Parallel Jacobian Benchmark Result

- Classification: `seven_volume_parallel_jacobian_meaningful_speedup`
- Decision: `authorize_persistent_parallel_step_solver_design`
- One-worker median Jacobian: `0.271654 s`
- Two-worker median Jacobian: `0.197377 s`
- Four-worker median Jacobian: `0.102903 s`
- Two-worker speedup: `1.376x`
- Four-worker speedup: `2.640x`
- Four-worker adjusted startup: `5.714203 s`
- Delegated thermo evaluations: `246` per matrix at every worker count
- Projected production path: `55.742 s` wall per `30 s` simulated
- Benchmark wall: `94.275 s`
- Gates: `{'frozen_schedule': True, 'color_and_task_count': True, 'process_isolation': True, 'matrix_absolute': True, 'matrix_relative': True, 'spectrum': True, 'rank_and_condition': True, 'meaningful_four_worker_speed': True, 'projected_production_wall': True, 'benchmark_wall': True, 'no_solve_or_state_advance': True}`

All nine matrices have equivalent values, rank, condition, and singular spectra.
The benchmark evaluated complete seven-volume colored-Jacobian perturbations in
isolated DWSIM processes. It performed no nonlinear solve or state advance.

The speedup is useful only with a persistent worker pool. Recreating four DWSIM
workers for every Jacobian would add about `5.7 s` to work that takes about
`0.103 s` once the workers are ready. DD-181 therefore authorizes design of a
persistent parallel step solver, not repeated pool creation and not a new
trajectory.
