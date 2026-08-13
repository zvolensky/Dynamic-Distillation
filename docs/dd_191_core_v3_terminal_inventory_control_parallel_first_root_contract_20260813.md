# DD-191 Controlled Parallel First-Root Contract

- Payload SHA-256: `649a355b8e6f3cde0f379d0fe04d9466ae9be0896be4b7d31f5e034261ef51ce`
- Preparation base commit: `d236a046225da53c8598da7497f8cd0446555193`
- Root: first controlled `0.125 s` refined step
- Matrix: `58 x 58`, `17` colors, `34` perturbation tasks
- Comparison: serial in-process versus four isolated DWSIM workers
- Equivalence: Jacobians, SciPy decisions, and all endpoint quantities
- Performance: parallel solve excluding startup at least `10%` faster
- Endpoint acceptance, second timestep, trajectory, tuning, and retry: prohibited
