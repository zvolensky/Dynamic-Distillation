# DD-144 Frozen Post-Cache-Fix Captured Short-Trajectory Contract

- Payload SHA-256: `0edec3a226af7a0d2b4a4ce073cec99123de3d9e4c380e4a655a1595d35a21b5`
- Scientific contract changes from DD-134: `none`
- Cache: DD-142 exact-state property keys
- Solver: DD-137 immutable captured modified Newton
- Duration/grids: `10 s`, `10 x 1.0 s`, and `20 x 0.5 s`
- Complete per-step Jacobian, residual, correction, and line-search capture: required
- Provider-call limit: `<80000`
- Wall-clock limit: `<180 s`
- Rebuild, alternate solver, retry, fallback, clipping, projection, or grid change: prohibited

Passing may authorize a separately frozen trajectory extension. Failure stops with replay-complete evidence.
