# DD-149 Parallel Captured Short-Trajectory Result

- Classification: `parallel_captured_short_trajectory_equivalent`
- Decision: `authorize_separately_frozen_modest_parallel_trajectory_extension`
- Completed roots: `30`
- Worker calls/tasks: `35280` / `1260`
- Capture differences: `{'dd134:coarse': 0.0, 'dd134:refined': 0.0}`
- Accepted-step differences: `{'coarse': 0.0, 'refined': 0.0}`
- Pool startup: `6.193 s`
- Total wall: `22.949 s` (`0.473x` DD-144)
- Gates: `{'source_scientific_gates': True, 'one_persistent_pool': True, 'worker_process_ownership': True, 'complete_root_capture': True, 'exact_task_count': True, 'exact_parallel_provider_calls': True, 'captured_serial_equivalence': True, 'accepted_step_serial_equivalence': True, 'meaningful_total_wall_improvement': True, 'absolute_wall': True, 'no_rebuild_retry_fallback_or_grid_change': True}`

The exact DD-144 coarse/refined science is retained. One persistent process-isolated DWSIM pool supplies all Jacobians, while residuals, globalization, and state acceptance remain in the main process.
