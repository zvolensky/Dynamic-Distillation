# DD-148 Parallel Captured First-Root Result

- Classification: `parallel_captured_first_root_equivalent`
- Decision: `authorize_separately_frozen_parallel_captured_short_trajectory_contract`
- Serial/parallel Jacobian wall: `0.554112 s` / `0.213437 s`
- Matrix difference: `0.000000000e+00`
- Final coordinate difference: `0.000000000e+00`
- Final residual difference: `0.000000000e+00`
- DD-146 reproduction: `{'matrix_max_abs': 0.0, 'final_coordinate_max_abs': 0.0, 'final_residual_max_abs': 0.0}`
- Pool startup: `5.104 s`
- Total wall: `10.887 s`
- Gates: `{'two_captured_solves': True, 'both_converged': True, 'process_isolation': True, 'parallel_calls': True, 'exact_matrix_equivalence': True, 'captured_root_equivalence': True, 'dd146_reproduction': True, 'rank_and_condition': True, 'residual_identity': True, 'complete_capture': True, 'main_provider': True, 'wall': True, 'no_state_acceptance_or_retry': True}`

The root is reconstructed for integration evidence only. No endpoint is accepted and no timestep or trajectory occurs.

## Equivalence

Serial and parallel captured evidence agrees exactly:

- initial residual difference: `0.0`;
- frozen Jacobian difference: `0.0`;
- correction difference: `0.0`;
- line-search trial coordinate difference: `0.0`;
- line-search trial residual difference: `0.0`;
- final coordinate difference: `0.0`;
- final residual difference: `0.0`;
- trial decisions and solver metadata: identical.

Both roots converge to residual `1.087532713e-10`. The parallel matrix, final coordinates, and final residual also reproduce the accepted DD-146 evidence exactly. Rank remains `50/50`, condition remains unchanged, all four workers participate, and the parallel matrix uses exactly `1,176` governing provider calls.

## Timing

The integrated serial Jacobian takes `0.554112 s`; the four-worker Jacobian takes `0.213437 s`, a `2.596x` speedup. Pool startup takes `5.104 s` and is intended to be amortized over a trajectory. The complete two-root integration proof finishes in `10.887 s`.

## Decision

The process-isolated parallel Jacobian is solver-equivalent at the first implicit root. One separately frozen parallel captured short-trajectory contract is authorized. That successor must keep one persistent pool, retain complete per-step capture, and compare its endpoint against the accepted serial DD-144/DD-145 trajectory before authorizing longer operation.
