# DD-182 Seven-Volume Parallel First-Root Result

- Classification: `persistent_parallel_first_root_exact_and_faster`
- Decision: `authorize_persistent_parallel_short_trajectory_contract`
- Serial/parallel residual: `1.192235e-12` / `1.192235e-12`
- Serial/parallel `nfev,njev`: `4,4` / `4,4`
- Jacobian evaluations: `4` each
- Worst paired Jacobian difference: `0.000000e+00`
- Final-coordinate difference: `0.000000e+00`
- Serial/parallel solve wall: `1.252650 s` / `0.534514 s`
- Parallel solve speedup excluding startup: `2.344x`
- Persistent-pool startup: `5.010 s` adjusted
- Worker logical property requests: `4,624`
- Gates: `{'root_success': True, 'root_residual': True, 'root_rank_condition': True, 'jacobian_count': True, 'every_jacobian_exact': True, 'solver_decisions_exact': True, 'endpoint_equivalence': True, 'process_isolation': True, 'task_ownership': True, 'provider': True, 'provider_calls': True, 'meaningful_speed': True, 'wall_clock': True, 'no_state_advance_or_controller': True}`

The main process retained the same SciPy residual, trust-region decisions, convergence test, and endpoint evaluation. Only colored-Jacobian perturbation residuals were delegated. No endpoint was accepted as a state advance.

Every corresponding Jacobian, final coordinate, final residual, endpoint
inventory, component rate, algebraic coordinate, and energy-storage quantity
has an absolute serial/parallel difference of exactly `0.0`. This result
authorizes a separately frozen short trajectory using one persistent pool. It
does not authorize controller implementation or a longer trajectory.
