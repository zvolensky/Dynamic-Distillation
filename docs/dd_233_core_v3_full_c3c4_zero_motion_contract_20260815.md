# DD-233 Full-C3/C4 Zero-Motion Contract

- Payload SHA-256: `94f69658b7bfec674b8ba93825008cc9e8b5953b5df235039e55311560db28ba`
- State: accepted DD-231 20-stage stationary root
- Dynamic system: controlled constant-step BDF2, `162 x 162`
- History timestep: `0.25 s`
- Histories: accepted inventory/energy/memory repeated at both levels
- Thermo: DWSIM fugacity/enthalpy; aligned-PR liquid density
- Jacobians: colored central differences at `1e-5` and `5e-6`
- Direct sentinel columns: `15`
- Solve, accepted timestep, controller advance, or integration: `False`

One execution is permitted after this contract is committed.
