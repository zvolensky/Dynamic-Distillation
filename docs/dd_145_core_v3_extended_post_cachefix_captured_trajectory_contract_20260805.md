# DD-145 Frozen Extended Post-Cache-Fix Captured-Trajectory Contract

- Payload SHA-256: `7257bafc87ce1b588b739478e5b81dbefda177a24578f31e4867bf5d392ae196`
- Sole scientific change from DD-144: duration `10 s -> 20 s`
- Initial state/controller move: exact DD-144
- Grids: `20 x 1.0 s` and `40 x 0.5 s`
- Solver: one frozen 21-color Jacobian and factorization per root
- Complete immutable per-step evidence: required
- Provider-call limit: `<80000`
- Wall-clock limit: `<180 s`
- Rebuild, alternate solver, retry, fallback, clipping, projection, or controller change: prohibited

Passing may authorize only a separately frozen longer trajectory contract. Failure stops with replay-complete evidence.
