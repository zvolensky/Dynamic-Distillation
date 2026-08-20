# DD-237 C3/C4 Vapor-Holdup Geometry

- Classification: `c3c4_vapor_geometry_passed`
- Decision: `authorize_live_vapor_property_and_eos_residual_implementation`
- Stages/feed stage: `20 / 12`
- Mapped control volumes: `20`
- Structural ledger: `258 x 258`
- Structural rank: `258`
- Top drum gross capacity: `5101.729438 ft3`
- Combined bottom gross capacity: `3405.501240 ft3`
- Capacity range: `338.945707` to `5101.729438 ft3`

Free vapor volume is not fixed at these capacities. At a live state:

`V_free[j] = gross_capacity[j] - sum_k(N_L[j,k]) / rho_L[j]`

No property call, endpoint free-volume evaluation, residual, solve, timestep, or trajectory occurred.
