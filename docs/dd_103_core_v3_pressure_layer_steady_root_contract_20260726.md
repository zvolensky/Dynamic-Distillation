# DD-103 Frozen Core V3 Pressure-Layer Steady-Root Contract

- Payload SHA-256: `b7fdba6296e37b41d3c6c36175471d615c56eb0783cb5260e7542a8399ac6907`
- Preparation base commit: `03558c9bc382b199d875e49b7e7e301c8e166a05`
- Residual system: `42` equations with all `15` rates fixed at zero
- Solve coordinates: `27` algebraic variables
- Structural Jacobian colors: `14`
- Starts: accepted-root algebraic state and independent source-profile state
- Solver: bounded `least_squares(method='trf')`
- Governing Jacobian: frozen colored central difference
- Endpoint Jacobians: full central differences at `1e-5` and `5e-6`
- Live property evaluation during preparation: `False`
- Nonlinear solve during preparation: `False`
- Dynamic integration during preparation: `False`

## Bottom Boundary Decision

The combined reboiler/sump link is dry-resistance-only. Merged sump inventory is not converted into tray liquid head. The remaining three tray links retain dry plus liquid-head closure. This rule is based on terminal link role and contains no stage-number condition.

## Hard Stop

Both starts must reach one common, interior, ordered-pressure root with scaled residual below `1e-8`, full algebraic column rank, stable endpoint spectra, exact conservation, and declared provider ownership. No tuning, continuation, alternate geometry, or rerun follows failure.
