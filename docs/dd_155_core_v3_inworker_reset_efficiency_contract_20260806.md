# DD-155 Frozen In-Worker Thermo Reset Efficiency Contract

- Payload SHA-256: `9527e2487218312d3d4edf30f8c38b22ed7a1ce82f7282f3b5f25956f6efa7af`
- Aging workload: one persistent four-worker pool, saved DD-151 coarse roots `2..180`
- Probe: root `180`, two matrices per stage
- Stages: no reset, Python cache clear, provider reconstruction, DWSIM backend reinitialization
- Exact work: 187 matrices, 7,854 tasks, 219,912 worker-evaluation calls, 232 reset calls
- Matrix reproduction: `<=1e-10` absolute
- Aging gate: no-reset/fresh `>=1.20`
- Recovery gate: reset/fresh `<=1.15` and no-reset/reset speedup `>=1.20`
- Wall limit: `<180 s`

The DWSIM reset directly clears process-local backend objects for diagnosis only. Passing may authorize a separately implemented and frozen reset API plus saved-state equivalence proof. No trajectory is authorized.
