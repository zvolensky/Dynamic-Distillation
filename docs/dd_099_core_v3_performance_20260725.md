# DD-099 Core V3 Performance-Correction Result

## Decision

DD-099 passes every frozen numerical and performance gate in its single
execution from contract commit `289b451`.

The corrected implicit residual and the structurally colored Jacobian are
accepted for the next bounded Core V3 open-loop contract. This does not
authorize controllers, pressure dynamics, vapor holdup, or production-scale
integration.

## Corrections validated

The former backward-Euler residual evaluated the full governing property
packet and then solved five additional bubble problems to reconstruct energy
storage. The corrected residual uses the liquid enthalpy and density already
evaluated at each trial endpoint. Density is now present for all five volumes,
including the terminal volumes.

This is both a performance and formulation correction. Internal energy is now
computed at the simultaneous trial `N/T/P/x` state instead of at a separately
projected saturated state inside the nonlinear residual.

The backward-Euler structural pattern also includes the chain from each trial
component rate through endpoint inventory to every state-dependent equation.
Its 38 columns require 17 conflict-free colors, reducing a central Jacobian
from 76 residual evaluations to 34.

## Numerical result

Four independent `1.0 s` solves were executed from the accepted DD-094 root:

| Case | Jacobian | Calls | Wall time (s) | Residual inf norm | Rank | Condition |
|---|---:|---:|---:|---:|---:|---:|
| Root hold | Uncolored | 3,768 | 4.173 | `2.00e-13` | 38 | `1.833e5` |
| Root hold | Colored | 1,752 | 1.069 | `2.00e-13` | 38 | `1.833e5` |
| `+0.1%` feed | Uncolored | 9,288 | 4.006 | `8.90e-14` | 38 | `1.833e5` |
| `+0.1%` feed | Colored | 4,248 | 2.025 | `8.90e-14` | 38 | `1.833e5` |

Colored and uncolored endpoints, rates, temperatures, algebraic coordinates,
and final Jacobians are identical to reported precision in both cases. The
root remains stationary. The feed step produces the expected nonzero response
with maximum component rate `3.4181 lbmol/h`.

All physical, component-conservation, energy-conservation, equilibrium,
provider-ownership, and no-fallback gates pass. No implicit residual call uses
`bubble_temperature_and_incipient_vapor`.

## Performance result

DD-098 used `325,332` provider calls for eight endpoints, or `40,666.5` calls
per endpoint. DD-099's colored method averages `3,000` calls per solve, a
`13.5555x` reduction. Total wall time for all four comparison solves is
`16.394 s`.

The condition number is higher than DD-098's approximately `35` because the
new residual differentiates actual trial-state internal energy instead of a
nested saturation projection. It remains full rank and more than 500 times
below the frozen `1e8` limit.

## Authorization

One separately frozen modest longer open-loop trajectory may be drafted using:

- governing-property energy storage;
- the validated 17-color central Jacobian;
- unchanged physical equations, provider ownership, solver tolerances, and
  acceptance gates.

Longer production trajectories and controller work remain unauthorized until
that bounded trajectory passes.
