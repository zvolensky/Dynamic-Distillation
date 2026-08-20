# DD-254 Persistent-Parallel Vapor-Holdup Trajectory Contract

- Payload SHA-256: `57fe7d9bb5967c1d46854213e21cf6e5f580ab3d0f89f85cf44a1197e3a65000`
- Paths: four serial and four persistent-parallel `0.25 s` endpoints.
- Disturbance: unchanged DD-249 `+0.1%` feed and enthalpy.
- Pool: one persistent eight-worker DWSIM process pool.
- Each accepted endpoint supplies the next worker reference basis.
- Jacobian, solver-decision, endpoint, conservation, physical, and provider equivalence are required.
- Parallel path excluding startup must be at least 25% faster.
- Retry, alternate grid, controller, or longer trajectory: `False`.
