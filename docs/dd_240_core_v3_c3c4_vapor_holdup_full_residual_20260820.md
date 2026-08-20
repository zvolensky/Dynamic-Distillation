# DD-240 Full Vapor-Holdup Residual

- Classification: `vapor_holdup_full_residual_ready_for_jacobian`
- Decision: `authorize_two_step_colored_jacobian_audit`
- Numerical ledger: `258 x 258`
- Liquid balance maximum: `1.055384e-09 lbmol/h`
- Vapor balance maximum: `1.818989e-12 lbmol/h`
- Fugacity maximum: `3.996803e-15`
- Relative EOS maximum: `4.036427e-16`
- Energy maximum: `1.225155e-06 BTU/h`
- Francis maximum: `2.364686e-11 lbmol/h`
- Pressure-drop maximum: `6.204243e-01 psia`
- Jacobian colors: `28`
- Governing property calls: `120`

The inherited stationary blocks close. Pressure drop does not close because the DD-231 root used a prescribed pressure profile. That visible mismatch is the physical work assigned to the successor pressure/flow equations.

No nonlinear solve, accepted timestep, or integration occurred.
