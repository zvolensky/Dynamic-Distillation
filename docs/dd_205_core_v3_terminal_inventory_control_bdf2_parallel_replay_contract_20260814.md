# DD-205 Persistent-Parallel BDF2 Replay Contract

- Payload SHA-256: `30b71b5ba3bb7c945033e4f4c3b384aed4ace34cd5a66939d3d73eb043461982`
- Preparation base commit: `f3030b83a08ee4246de88372c0e8dd2b820956fd`
- Replay: exact DD-202 `40 x 0.25 s` and `80 x 0.125 s` paths
- Execution: one persistent four-worker DWSIM pool for all 120 roots
- Saved-result absolute agreement: `1e-12`
- Required trajectory speedup: `1.1x`
- In-execution deadline: `180.0 s`
- No equation, property, controller, solver, grid, tolerance, or fallback change is authorized.

Commit this immutable contract before its one execution.
