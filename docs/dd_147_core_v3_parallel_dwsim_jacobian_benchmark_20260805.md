# DD-147 Parallel DWSIM Jacobian Benchmark Result

- Classification: `parallel_dwsim_jacobian_meaningful_speedup`
- Decision: `authorize_parallel_colored_jacobian_integration_contract`
- Serial median Jacobian: `0.813660 s`
- Two-worker median/speedup: `0.417453 s` / `1.949x`
- Four-worker median/speedup: `0.225274 s` / `3.612x`
- Four-worker time ratio: `0.276865` (limit `<=0.60`)
- Projected DD-146 wall: `42.126 s` (limit `<75 s`)
- Benchmark wall: `107.473 s`
- Gates: `{'frozen_schedule': True, 'color_and_task_count': True, 'process_isolation': True, 'provider_calls': True, 'matrix_absolute': True, 'matrix_relative_frobenius': True, 'singular_spectrum': True, 'rank_and_condition': True, 'timing_monotonic': True, 'meaningful_four_worker_speed': True, 'projected_dd146_wall': True, 'benchmark_wall': True, 'no_solve_or_state_advance': True}`

The benchmark evaluates complete colored-Jacobian perturbation residuals in isolated DWSIM worker processes. It performs no nonlinear solve or state advance.

## Numerical Integrity

All nine complete matrices are bit-for-bit identical to the accepted DD-146 matrix:

- maximum absolute difference: `0.0`;
- maximum relative Frobenius difference: `0.0`;
- maximum singular-spectrum difference: `0.0`;
- rank: `50/50` in every run;
- condition: `2.084320550e5` in every run;
- provider calls: exactly `1,176` per matrix and `28` per perturbation task;
- process participation: exactly `1`, `2`, and `4` distinct task workers as contracted.

The independently initialized process-local providers therefore preserve the repaired exact-state cache semantics and governing DWSIM property results under concurrent execution.

## Timing

Median warmed-Jacobian times are:

- one worker: `0.813660 s`;
- two workers: `0.417453 s`, or `1.949x` speedup;
- four workers: `0.225274 s`, or `3.612x` speedup.

The four-worker time ratio is `0.276865`, comfortably below the `0.60` acceptance limit. Median adjusted four-worker pool startup is `6.085 s`. Using the frozen DD-146 Jacobian call fraction, the projected DD-146-equivalent wall time is `42.126 s`, versus the measured serial `116.259 s` and the `<75 s` gate.

## Decision

Process-isolated DWSIM evaluation is both scientifically exact and operationally meaningful for the colored Jacobian. One separately frozen integration contract may connect the four-worker evaluator to the captured modified-Newton trajectory while preserving serial assembly order, complete failure evidence, and an immediate serial/parallel first-root equivalence gate. This benchmark does not itself change the production solver.
