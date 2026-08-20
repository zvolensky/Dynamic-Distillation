# DD-252 Vapor-Holdup Parallel First-Root Result

- Classification: `vapor_holdup_parallel_first_root_failed`
- Decision: `retain_serial_vapor_holdup_solver`
- Serial/parallel residual: `3.938833e-13` / `3.938833e-13`
- Serial/parallel `nfev,njev`: `12,6` / `12,6`
- Jacobian evaluations: `6` each
- Jacobian/coordinate difference: `0.000000e+00` / `0.000000e+00`
- Serial/parallel solve wall: `6.273416 s` / `3.803538 s`
- Parallel solve speedup: `1.649x`
- Adjusted worker startup: `8.373 s`
- Gates: `{'root_success': True, 'root_residual': True, 'rank': True, 'condition': True, 'solver_decisions': True, 'jacobian_count': True, 'jacobian_equivalence': True, 'coordinate_equivalence': True, 'residual_equivalence': True, 'process_isolation': False, 'worker_tasks': True, 'provider': True, 'provider_calls': False, 'meaningful_speed': True, 'wall_clock': True, 'no_state_advance': True}`
- State advance, retry, controller, or trajectory: `False`
