# DD-151 Parallel Captured Five-Minute Trajectory Result

- Classification: `parallel_captured_five_minute_trajectory_failed`
- Decision: `stop_with_replay_complete_multiminute_evidence`
- Completed coarse/refined roots: `300` / `600`
- Total roots: `900`
- Worker calls/tasks: `1058400` / `37800`
- DD-146 prefix capture differences: `{'dd134:coarse': 0.0, 'dd134:refined': 0.0}`
- DD-146 prefix accepted-step differences: `{'coarse': 0.0, 'refined': 0.0}`
- Endpoint refinement: `{'inventory': 1.621834509914248e-06, 'energy': 1.602904692434366e-06, 'memory': 1.0454337595888763e-06, 'coordinates': 5.717828751999887e-06, 'product': 5.7164154925351096e-06, 'level': 8.454078137543064e-07}`
- Capture storage: `full_replay`
- Pool startup: `7.250 s`
- Governed wall: `476.349 s` (`7.153x` DD-150)
- Gates: `{'source_scientific_gates': False, 'one_persistent_pool': True, 'worker_process_ownership': True, 'complete_root_capture': True, 'immutable_capture': True, 'exact_task_count': True, 'exact_parallel_provider_calls': True, 'captured_serial_equivalence': True, 'accepted_step_serial_equivalence': True, 'meaningful_total_wall_improvement': False, 'absolute_wall': False, 'no_rebuild_retry_fallback_or_grid_change': True}`

The first 60 seconds reproduce DD-146 exactly. Successful full captures are represented by deterministic per-root digests; a failed campaign would retain full replay evidence.
