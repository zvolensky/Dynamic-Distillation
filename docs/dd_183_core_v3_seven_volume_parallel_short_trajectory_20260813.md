# DD-183 Seven-Volume Persistent-Parallel Short-Trajectory Result

- Classification: `persistent_parallel_short_trajectory_exact_and_faster`
- Decision: `authorize_persistent_parallel_production_step_path`
- Roots: `16` serial / `16` parallel
- Jacobians per path: `56`
- Worst paired Jacobian difference: `0.000000e+00`
- Worst accepted-state difference: `0.000000e+00`
- Serial/parallel trajectory wall: `23.359 s` / `12.480 s`
- Parallel trajectory speedup excluding startup: `1.872x`
- Adjusted startup: `1.875 s`
- Governed speedup including startup: `1.627x`
- Worst serial/parallel residual: `1.504662e-12` / `1.504662e-12`
- Worker logical property requests: `66,912`
- Actual/expected response: `0.007936637767` / `0.007936637778 lbmol`
- Gates: `{'paths_complete': True, 'scientific_steps': True, 'response': True, 'monotone_response': True, 'jacobian_count': True, 'every_jacobian_exact': True, 'solver_decisions_exact': True, 'accepted_states_equivalent': True, 'process_isolation': True, 'task_ownership': True, 'evolving_basis': True, 'provider': True, 'provider_calls': True, 'parallel_trajectory_speed': True, 'governed_speed_including_startup': True, 'wall_clock': True, 'no_controller_or_retry': True}`

One persistent four-process DWSIM pool supplied every parallel Jacobian while the main process retained all residual, trust-region, convergence, and state-acceptance decisions. No controller, retry, alternate grid, projection, clipping, or fallback occurred.

Each of the 16 evolving roots rebuilt its inventory, internal-energy storage,
rate scales, and physical-state template exactly once in every worker on the
root's first Jacobian. No worker rebuilt or reused that basis incorrectly on
later Jacobians. All 56 paired Jacobians, SciPy decisions, and accepted states
have exactly zero serial/parallel difference.

DD-183 authorizes the persistent four-worker DWSIM Jacobian path for production
step execution. It does not by itself authorize terminal controller equations
or a longer controlled trajectory.
