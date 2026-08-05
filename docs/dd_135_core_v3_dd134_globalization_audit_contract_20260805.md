# DD-135 Frozen DD-134 Globalization Audit Contract

- Payload SHA-256: `aaf7d1e37c5a1e74f00843fc220d0aa1a2aa2df307834c2747433d361c3cd737`
- Evidence points: saved DD-134 coarse `t=7 s` and refined `t=3 s` failures
- Comparison: original root-start Jacobian versus fresh stalled-point Jacobian
- Trial fractions: `1, 0.5, 0.25, 0.125`
- Residual equations, scales, bounds, provider, and finite-difference step: unchanged
- State acceptance, root completion, timestep, and trajectory: prohibited
- Provider-call limit: `<7000`
- Wall-clock limit: `<180 s`

The audit distinguishes stale-Jacobian globalization loss from a residual/provider floor. It does not retry DD-134 or authorize a trajectory.
