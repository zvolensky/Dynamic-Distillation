# DD-183 Seven-Volume Persistent-Parallel Short-Trajectory Contract

- Payload SHA-256: `a184192d3c523e27ea0d9563885d6d411d40a40d91a8ada2f9c837228c44317a`
- Disturbance: unchanged `+0.1%` feed rate and enthalpy
- Paths: one serial and one persistent four-worker parallel
- Grid: `16 x 0.25 s = 4.0 s` per path
- Equivalence: every Jacobian exact; every accepted state within `1e-12`
- Performance: parallel trajectory `<=65%` serial excluding startup
- Governed performance: parallel plus startup `<=85%` serial
- Controller, retry, alternate grid, clipping, projection, and fallback: prohibited
