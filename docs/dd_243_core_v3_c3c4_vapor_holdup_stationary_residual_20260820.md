# DD-243 Full Stationary Vapor-Holdup Residual

- Classification: `vapor_holdup_stationary_residual_ready_for_jacobian`
- Decision: `authorize_stationary_two_step_colored_jacobian_audit`
- Numerical ledger: `260 x 260`
- Scaled residual maximum: `6.204243e-01`
- Pressure-drop maximum: `6.204243e-01 psia`
- Terminal inventory residuals: `[0.0, 0.0]` lbmol
- Relative vapor-EOS maximum: `4.036427e-16`
- Colored Jacobian groups: `28`
- Nonlinear solve or timestep: `False`

## Meaning

The stationary equations are fully implemented. The inherited starting point already satisfies equilibrium, EOS, mass, energy, and terminal-level equations to numerical precision. Its prescribed pressure profile still misses the live pressure-drop equations, which is the intended work for a future stationary solve.
