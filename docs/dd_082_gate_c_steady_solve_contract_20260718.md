# DD-082 Gate C Steady-Solve Contract

## Decision Scope

DD-082 is one fixed nonlinear solver campaign with exactly three predefined
starts. It is not three rounds of solver development.

The campaign uses the unchanged DD-081 `38 x 38` residual and the same:

- topology and equation ownership;
- live DWSIM PR property calls;
- direct `NL/x` reconstruction;
- residual scales;
- prescribed pressures and section vapor rates;
- reflux, feed, duties, and terminal liquid targets;
- Francis geometry and coefficients;
- absolute-step colored central-difference Jacobian.

## Solver

```text
scipy.optimize.least_squares
method             = trf
loss               = linear
x_scale            = jac
Jacobian step      = 1e-5
ftol/xtol/gtol     = 1e-12
max_nfev           = 300
```

No continuation, alternate method, regularization residual, fallback
property, projection, or post-result parameter change is implemented.

## Fixed Bounds

| Coordinate family | Bounds |
|---|---|
| component inventories | `0.02x` to `50x` reference |
| internal-energy coordinate | `-5` to `+5` |
| temperature | `80 F` to `300 F` |
| vapor logit change | `-8` to `+8` |
| liquid and product flow | `0.05x` to `20x` reference |

An accepted root may not have an active coordinate bound.

## Predefined Starts

1. Canonical mini8-derived DD-081 seed.
2. Existing deterministic bounded combined perturbation.
3. Independent smooth physical profile.

The independent profile uses:

- terminal liquid compositions only;
- log-ratio composition interpolation;
- linear terminal-temperature interpolation;
- live density and a fixed `0.35 ft` target over-weir head for interior
  inventories, limited only by tray spacing;
- live DWSIM internal energy and local equilibrium reconstruction;
- live Francis flows;
- terminal product estimates from total and light-component feed closure.

It does not use mini8 interior temperature, composition, inventory, liquid
flow, or vapor composition as the answer.

## Acceptance

Every start must:

- report solver convergence;
- reach scaled residual infinity norm below `1e-8`;
- retain numerical rank `38/38` at `h` and `h/2`;
- retain condition below `1e8`;
- preserve DD-081 component and energy telescoping tolerances;
- remain positive and finite;
- keep hydraulic liquid heights below tray spacing;
- use no clipping, projection, fallback, or active bound.

Every pair of roots must agree below `1e-7` under the declared normalized
physical-state comparison.

## Hard Stop

If any start fails, roots disagree, rank is lost, conditioning exceeds the
limit, a bound is active, or the residual remains above tolerance, Gate C
fails. No DD-083 solver tuning, continuation variant, geometry adjustment, or
second operating-specification campaign is authorized.

