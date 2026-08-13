# DD-193 Controlled Finer-Grid Parallel Trajectory Result

- Classification: `controlled_finer_parallel_trajectory_aborted_on_wall_hard_stop`
- Decision: `retire_dd193_without_retry_and_require_incremental_worker_audit_before_future_fine_grid_work`
- Frozen wall limit: `240 s`
- Observed elapsed before operator stop: at least `1503 s` (`6.2625x` the limit)
- Parent and four worker processes: stopped and verified
- Complete campaign result artifact: not produced
- Scientific trajectory/refinement gates: not evaluated
- Endpoint state: not available and not claimed
- Retry, tuning, alternate grid, or longer horizon: not attempted

## Diagnosis

The processes remained active and CPU-bound; this was not an idle deadlock. The
DD-193 worker called `ProviderCallAudit.report()` after every colored
perturbation task. That method rescans the complete accumulated record list for
violations and rebuilds grouped counts. Repeating it after thousands of tasks
causes cumulative provenance bookkeeping to grow superlinearly with trajectory
length.

DD-193 is retired without retry. It establishes an execution/reporting scaling
defect, not a thermodynamic, controller, conservation, or timestep-convergence
failure. Before any successor, worker ownership evidence must be collected
incrementally and the wall hard stop must be enforced during execution.
