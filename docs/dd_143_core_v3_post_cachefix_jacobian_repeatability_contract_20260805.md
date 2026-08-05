# DD-143 Frozen Post-Cache-Fix Jacobian Repeatability Contract

- Payload SHA-256: `24ee6730118be5fea1b8d902779cf819cbe6fe5984beef126ab594e80bf7ffd3`
- Matrices: `12` complete `50 x 50` matrices
- Points/steps: coarse and refined roots at `1e-5` and `5e-6`
- Processes: grouped-forward, grouped-reverse, and interleaved
- Cross-process matrix limits: `1e-10` absolute and relative Frobenius
- Nonlinear solve, correction, state advance, timestep, and trajectory: prohibited
- Provider-call limit: `<20000`
- Wall-clock limit: `<180 s`

This is a post-fix numerical proof only. It cannot accept a simulation state.
