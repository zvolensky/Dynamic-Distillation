# DD-182 Seven-Volume Parallel First-Root Contract

- Payload SHA-256: `074a30e28c427b943d772fcc94ad3610202208cda0abf30af297cf820edf0d74`
- Root: DD-180 first `0.25 s` coarse implicit root
- Solves: one serial and one persistent four-worker parallel root
- Main process: identical SciPy residual, trust-region, and acceptance path
- Delegated work: only 17-color central-difference perturbation residuals
- Equivalence: every requested Jacobian exact; endpoint within `1e-12`
- Performance: parallel solve excluding startup at least `10%` faster
- State acceptance, second timestep, controller, trajectory, and retry: prohibited
