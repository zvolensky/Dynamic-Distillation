# DD-234 Full-C3/C4 Stationary Hold Contract

- Payload SHA-256: `4cf99a3f61fbe414800164ef17063e2ccc28284d24465da3d3cb08e834209006`
- Solver: `least_squares(method=trf)` with colored central differences
- Comparison: one `0.25 s` backward-Euler step versus two `0.125 s` steps
- State and controller setpoints: exact accepted DD-233 handoff
- Thermo: DWSIM fugacity/enthalpy; aligned-PR liquid density
- DD-233 coordinate scale reused without modification
- Disturbance, tuning, retry, or trajectory: `False`

Commit this immutable contract before its one live execution.
