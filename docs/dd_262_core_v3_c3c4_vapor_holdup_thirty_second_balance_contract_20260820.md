# DD-262 Thirty-Second Balance Adjudication Contract

- Payload SHA-256: `1b93f3a9ee8694e8ae31516c866ae676ee7eb2fdd22fd03f7e52b49398c95df8`
- DD-261 remains formally failed and unchanged.
- Replay exactly 120 saved endpoints with live DWSIM properties.
- Sum each endpoint's changing component and energy boundary rates over `0.25 s`.
- Compare those sums with the saved initial-to-final inventory and stored-energy changes.
- No nonlinear solve, timestep, state change, retry, controller, or alternate calculation is authorized.
