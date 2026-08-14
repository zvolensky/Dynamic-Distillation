# DD-204 Controlled BDF2 Serial/Parallel Equivalence Contract

- Payload SHA-256: `9641691c91893067da2bb5bba4bef2547d6daf959e3e5296cedf8dce1cfbb600`
- Preparation base commit: `e33a976188e7fce3b8559d2f40acba9bb3c5beb7`
- Live path: one `0.125 s` backward-Euler startup plus one `0.125 s` BDF2 root
- Comparison: in-process serial Jacobians versus one persistent four-worker DWSIM pool
- Matrix / endpoint limits: `1e-10` / `1e-12`
- Required solve speedup excluding startup: `1.1x`
- Call / governed-wall ceilings: `60000` / `180.0 s`
- Retry, alternate step, tuning, fallback, clipping, projection, and longer trajectory: prohibited

Commit this immutable contract before its one execution.
