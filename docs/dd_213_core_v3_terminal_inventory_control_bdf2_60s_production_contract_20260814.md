# DD-213 60-Second Production BDF2 Contract

- Payload SHA-256: `4962673e0e8e1857069f36637b2488cca4533f1f37c068282aa2af0b170e87a7`
- Coarse path: `240 x 0.25 s`
- Refined path: `480 x 0.125 s`
- Workers / BDF2 initial guess: `8` / `linear_extrapolation`
- Science: unchanged DD-209 disturbance, controllers, equations, solver, and DWSIM PR provider
- Refinement: frozen absolute physical/controller/response limits
- Logical provider-call ceiling: `3200000`
- Governed wall deadline: `300.0 s`
- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited

Commit this immutable contract before its one execution.
