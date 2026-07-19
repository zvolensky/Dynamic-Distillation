# DD-087 Saturated-Liquid Condenser Numerical-Audit Contract

## Purpose

DD-087 performs one frozen live-DWSIM numerical audit of the DD-086
solved-duty, saturated-liquid total-condenser architecture.

It answers only whether the live `40 x 40` residual is finite, conservative,
full rank, physically meaningful, and acceptably conditioned at two
precommitted states. It does not solve the full nonlinear system and does not
integrate dynamics.

## Bubble-Seed Decision

`ThermoProviderV1` does not expose a direct fixed-`(P,x)` DWSIM bubble-point
temperature and incipient-vapor API. DD-087 therefore uses one local frozen
`3 x 3` least-squares solve solely to construct the canonical boundary seed.

Its unknowns are:

```text
T_D
y_bubble additive-log-ratio coordinate 1
y_bubble additive-log-ratio coordinate 2
```

Its three residuals are the three full component fugacity equalities. The
method, bounds, finite-difference step, tolerances, maximum evaluations,
initial guess, and resulting seed are frozen in the JSON contract.

This local seed calculation is not a solve of any column balance, hydraulic
equation, duty equation, or full-system residual.

## Frozen Architecture

DD-087 retains DD-086 unchanged:

- five inventory locations;
- inventory-free total condenser;
- prescribed ordered pressure;
- prescribed feed, reflux, and reboiler duty;
- four energy-owned vapor links;
- full fugacity equilibrium at four column vapor outlets;
- Francis-only liquid hydraulics;
- solved `D/B`;
- prescribed terminal liquid amounts;
- solved condenser duty `Q_C`;
- saturated-liquid drum outlet with an incipient vapor composition.

No fixed condenser duty remains in the structural registry or live residual.

## Coordinates

The first `37` coordinates are identical to DD-084:

- five log liquid amounts;
- ten liquid-composition additive-log-ratio coordinates;
- five affine temperatures;
- eight vapor-composition additive-log-ratio coordinates;
- three log Francis liquid flows;
- four log vapor-link flows;
- log distillate and bottoms flows.

DD-087 adds:

- two additive-log-ratio coordinates for `y_bubble`;
- one signed affine coordinate for condenser duty.

The duty transform is:

```text
Q_C = Q_C,ref + s_Q * q_Q_C
```

where:

```text
s_Q = max(abs(Q_C,ref), abs(Q_R), abs(H_F))
```

No logarithmic transform is applied to negative heat-removal duty.

## Canonical Boundary

Preparation uses the declared drum liquid composition and pressure, solves
the local bubble equations, and computes:

```text
Q_C,ref = (R + D) * hL_D - V_top * hV_top
```

The result must have `Q_C,ref < 0`. The remaining physical reference values
are the DD-084 role-mapped seed; only the drum temperature is replaced by
the live bubble temperature.

The DD-085 hot-drum root is not used as a liquid seed.

## Frozen States

Exactly two complete transformed-coordinate vectors are committed before
the first full residual evaluation:

1. canonical saturated-liquid seed;
2. DD-084 deterministic combined perturbation plus fixed bounded
   perturbations to both bubble coordinates and `Q_C`.

Both must preserve positive amounts and flows, normalized positive
compositions, negative condenser duty, and bounded physical geometry.

## Residuals

The live residual contains exactly:

| Block | Rows |
|---|---:|
| Four column full-fugacity outlets | 12 |
| Five component balances | 15 |
| Five energy balances | 5 |
| Francis hydraulics | 3 |
| Terminal liquid specifications | 2 |
| Drum bubble fugacity | 3 |
| **Total** | **40** |

The first `37` residual scales are inherited unchanged from the committed
DD-084/DD-085 scale vector. Each bubble-fugacity residual has scale `1`.

## Jacobian Rules

Each frozen state uses an uncolored central-difference Jacobian at:

```text
h   = 1.0e-5
h/2 = 5.0e-6
```

The numerical coupling threshold is `1.0e-7`. The full condition-number hard
stop is `1.0e8`.

The local bubble submatrix uses the three bubble rows and the columns:

```text
T[reflux_drum]
y_bubble_logit[reflux_drum,component 1]
y_bubble_logit[reflux_drum,component 2]
```

It must have rank `3/3` at both steps with no zero row or column.

## Acceptance Gate

Both states and both Jacobian steps must have:

- full numerical rank `40/40`;
- condition below `1.0e8`;
- local bubble rank `3/3`;
- no zero row or column;
- no coupling outside the DD-086 registry;
- finite fugacity, enthalpy, density, and residual values;
- positive normalized compositions;
- positive amounts and internal flows;
- negative condenser duty;
- liquid heights below tray spacing;
- component telescoping below `1.0e-12` relative;
- energy telescoping below `1.0e-10` relative;
- no clipping, projection, property fallback, limiter, controller, or
  profile forcing.

The direct local bubble solve must close all three imposed-phase fugacity
equations below `1.0e-10`.

During contract preparation, a bounded cross-check showed that DWSIM's TP
flash and its imposed-phase fugacity calls do not share a tighter endpoint:
the exact fugacity solution was reported by TP flash with
`sum(x*K)-1 = 1.47e-5`, `beta = 4.46e-4`, and incipient-composition difference
`1.22e-6`. Solving at the TP flash's own endpoint instead left a direct
fugacity residual of approximately `1.41e-4`. The two APIs therefore cannot
simultaneously meet the initially proposed `1e-6` cross-check tolerances.

Before the JSON contract is created, the independent TP diagnostic is frozen
as a near-boundary classification gate:

```text
abs(sum(x_D * K) - 1) <= 1.0e-4
beta                    <= 1.0e-3
max(abs(y_bubble - normalize(K*x_D))) <= 1.0e-5
```

These tolerances are one order of magnitude above the measured discrepancies,
not acceptance of an arbitrary two-phase state. The canonical state must not
classify as stable vapor. No further tolerance adjustment is permitted after
the JSON contract is generated.

The scaled residual norm is diagnostic, not an acceptance criterion.

## Ownership Checks

The audit explicitly requires:

- `Q_C` affects only the reflux-drum energy residual;
- no fixed `Q_C` parameter remains in the registry;
- all three bubble rows depend on drum temperature and both bubble
  composition coordinates;
- the DD-084 material and energy couplings remain intact;
- component and energy telescoping include the solved duty exactly once.

## Two-Commit Discipline

1. Commit the implementation, tests, this contract, and the generated JSON
   contract before any live `40 x 40` residual evaluation.
2. Execute the two-state audit exactly once from that committed contract.
3. Commit the result and decision without changing the frozen inputs.

Preparation may perform only the local bubble-seed calculation and its
independent TP phase diagnostic.

## Hard Stop

Any failed criterion freezes Core V2 at DD-085. Do not change tolerances,
scales, vectors, property package, specifications, duty ownership, phase
requirement, or finite-difference settings afterward. Do not run a full
nonlinear solve.

A pass authorizes only drafting and precommitting one bounded `40 x 40`
steady-root campaign. It does not authorize execution, dynamic integration,
pressure dynamics, vapor holdup, controllers, or production scaling.
