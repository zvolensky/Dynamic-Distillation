# DD-150 Parallel Captured 60-Second Trajectory Result

- Classification: `parallel_captured_longer_trajectory_equivalent`
- Decision: `authorize_separately_frozen_multiminute_parallel_trajectory`
- Completed coarse/refined roots: `60` / `120`
- Total captured roots: `180`
- Worker calls/tasks: `211680` / `7560`
- Capture differences: `{'dd134:coarse': 0.0, 'dd134:refined': 0.0}`
- Accepted-step differences: `{'coarse': 0.0, 'refined': 0.0}`
- Pool startup: `6.343 s`
- Total wall: `66.596 s` (`0.573x` DD-146)
- Gates: `{'source_scientific_gates': True, 'one_persistent_pool': True, 'worker_process_ownership': True, 'complete_root_capture': True, 'exact_task_count': True, 'exact_parallel_provider_calls': True, 'captured_serial_equivalence': True, 'accepted_step_serial_equivalence': True, 'meaningful_total_wall_improvement': True, 'absolute_wall': True, 'no_rebuild_retry_fallback_or_grid_change': True}`

The complete 60-second DD-146 coarse/refined trajectory is reproduced with one persistent process-isolated DWSIM pool. Main-process residual evaluation, globalization, and state acceptance remain unchanged.
