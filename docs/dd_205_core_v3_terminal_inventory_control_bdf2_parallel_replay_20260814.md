# DD-205 Persistent-Parallel BDF2 Replay Result

- Classification: `controlled_bdf2_parallel_replay_failed`
- Decision: `retain_serial_bdf2_trajectory_path`
- Completed roots: `120`
- Saved-result maximum difference: `0.000000e+00`
- DD-202 / parallel trajectory wall: `159.194887` / `77.766701 s`
- Trajectory speedup: `2.047x`
- Adjusted startup / governed wall: `1.860` / `93.154 s`
- Logical provider calls: `542640`
- Retry, tuning, alternate grid, or fallback: `False`

## Gate assessment

All 120 roots completed. Every root, physical refinement, accuracy, response,
worker-participation, worker-basis, provider, call, startup, trajectory-speed,
and governed-wall gate passed. The worst root residual remained
`8.375332e-12`, rank remained `58`, and the worst condition remained
`3.172745e7`.

The sole formal failure is `saved_result_equivalence`. Its comparator reported
zero numerical difference across 11,999 numeric leaves, but classified the
three diagnostic index fields at each of 40 shared times as metadata changes.
DD-202 read those index coordinates from JSON as lists; the newly computed
in-memory result supplied equivalent tuples. JSON serialization converts both
representations to the same arrays.

An independent property-free comparison of the two persisted JSON files finds
the complete `coarse`, `refined`, `shared_time_refinement`, `response`,
`cross_grid`, and `response_gates` objects exactly equal. This observation does
not reclassify DD-205. The result remains formally failed and shall not be
rerun. One separately frozen zero-call artifact adjudication is authorized.

## Performance result

The persistent pool reduced trajectory wall from DD-202's `159.194887 s` to
`77.766701 s`, a `2.047x` speedup. Adjusted worker startup was `1.860043 s`,
and total governed wall was `93.154234 s`. All 450 Jacobians used all four
workers, and all 120 roots recorded exactly four aggregate worker-basis
rebuilds. These results remain evidence pending the zero-call adjudication.
