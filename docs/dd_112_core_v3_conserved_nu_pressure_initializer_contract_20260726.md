# DD-112 Frozen Conserved N/U Pressure Initializer Contract

- Payload SHA-256: `84e687c306061e050384035b87eca7a37862dd0d5293593ee4032a2e905dac9a`
- Primal variables / exact constraints: `65 / 52`
- Constraint Jacobian colors: `21`
- Starts: DD-094 pressure profile and DD-103 pressure endpoint
- Solver: one `SLSQP` equality-constrained campaign
- Objective weights, state/rate/algebraic: `1 / 10 / 1`
- Live property evaluation during preparation: `False`
- Initializer execution during preparation: `False`

Execution is permitted once only after this exact contract is committed. No retry, alternate solver, changed weight, continuation, timestep, or dynamics is authorized.

## Frozen Selection Problem

The 52 constraints are not penalty terms. They remain exact SLSQP equality
constraints. The quadratic objective selects one point on their feasible
manifold using normalized weights:

| Objective block | Weight |
|---|---:|
| Conserved-state movement | 1 |
| Conserved rates | 10 |
| Algebraic movement | 1 |

Component inventories use `log(N/N_DD094)`. Lower internal energies use
affine coordinates scaled by their DD-096 magnitudes. Rate and algebraic
coordinates retain the validated DD-109/DD-103 normalization.

## Starts

1. DD-094 component/internal-energy storage with its original algebraic
   pressure profile.
2. The same component inventory with the DD-103 pressure endpoint and the
   corresponding live lower storage reported by DD-109.

Both starts are strictly inside the committed bounds. They must converge to
the same constrained optimum; one successful start is insufficient.

## Acceptance

Both endpoints must satisfy all 52 constraints below `1e-8`, agree below
`1e-6` in normalized coordinates, retain rank `52/52`, condition below
`1e8`, stable two-step spectra, registered coupling, colored/full agreement,
KKT stationarity below `1e-5`, interior bounds, ordered pressure, physical
flows and inventories, exact conservation, and provider provenance. The
campaign is capped at `150000` provider calls and `300 s` wall time.

A pass produces only an initializer candidate. A separate zero-time audit and
refined first-step gate remain mandatory before dynamics.
