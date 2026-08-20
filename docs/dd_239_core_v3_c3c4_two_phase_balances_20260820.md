# DD-239 C3/C4 Two-Phase Zero-Rate Balances

- Classification: `c3c4_two_phase_zero_rate_balances_passed`
- Decision: `authorize_full_vapor_holdup_residual_assembly`
- Maximum liquid component residual: `1.055384e-09 lbmol/h`
- Maximum vapor component residual: `0.000000e+00 lbmol/h`
- Maximum total component residual: `1.055384e-09 lbmol/h`
- Maximum energy residual: `9.220093e-08 BTU/h`
- Component telescoping error: `2.842171e-13 lbmol/h`
- Energy telescoping error: `0.000000e+00 BTU/h`
- Exact interphase cancellation: `True`

The accepted total balance is split into separate liquid and vapor equations. The stationary vapor equation determines local vapor-to-liquid phase transfer; that same transfer enters the liquid equation with the opposite sign.

Pressure-drop and Francis rows are not yet assembled into the complete 258-equation residual. No solve, timestep, or integration occurred.
