# DD-146 Frozen Longer Post-Cache-Fix Captured-Trajectory Contract

- Payload SHA-256: `f7f464c0e4701d72e81c10d2f9dcc0fb88ff9fb0df0fa19e47d185e8d8725733`
- Sole scientific change from DD-145: duration `20 s -> 60 s`
- Administrative change: provider-call limit `80000 -> 240000`
- Initial state/controller move: exact DD-145
- Grids: `60 x 1.0 s` and `120 x 0.5 s`
- Solver: one frozen 21-color Jacobian and factorization per root
- Complete immutable per-step evidence: required
- Wall-clock limit: `<180 s`
- Rebuild, alternate solver, retry, fallback, clipping, projection, or controller change: prohibited

This is the final brute-force fully captured extension. Passing may authorize only a separately frozen trajectory-efficiency design before multi-minute operation. Failure stops with replay-complete evidence.
