# DD-084 Energy-Owned Vapor Numerical-Audit Contract

## Purpose

DD-084 performs one frozen live-DWSIM residual and Jacobian audit of the
DD-083 energy-owned vapor-flow architecture. It does not solve the steady
system and does not integrate dynamics.

The campaign definition, code, coordinate transforms, scales, perturbations,
finite-difference steps, and hard stops must be committed before the first
live evaluation.

## Fixed Physical Form

The five inventory locations are selected by physical role:

1. reflux drum;
2. rectifying tray;
3. feed tray;
4. stripping tray;
5. combined reboiler/sump.

The total condenser remains inventory-free. Pressure, reflux, feed,
condenser duty, reboiler duty, geometry, and terminal liquid targets are
parameters. `D`, `B`, three Francis liquid flows, and four independent vapor
links are algebraic unknowns.

Each equilibrium outlet enforces all component fugacity equalities:

```text
ln(y[k] * phiV[k] / (x[k] * phiL[k])) = 0
```

No relative-only equilibrium row replaces the saturation condition.

## Fixed Coordinates

For the three-component case:

| Coordinate block | Transform | Count |
|---|---|---:|
| Five liquid amounts | log ratio to role-mapped seed | 5 |
| Five liquid compositions | additive logistic ratio | 10 |
| Five temperatures | affine, `100 F` scale | 5 |
| Four vapor compositions | additive logistic ratio | 8 |
| Three Francis flows | log ratio | 3 |
| Four vapor-link flows | log ratio | 4 |
| Distillate and bottoms | log ratio | 2 |
| **Total** | | **37** |

The terminal liquid amounts use the declared workbook targets. Interior
liquid amounts, compositions, temperatures, and flow references come from
role-selected workbook locations. Source profiles initialize coordinates but
do not enter a physical residual.

## Fixed Residuals and Scales

The `37` residuals are:

- `12` full fugacity equalities;
- `15` component balances;
- `5` energy balances;
- `3` Francis equations;
- `2` terminal liquid-amount specifications.

Scales are fixed from declared operating magnitudes and the canonical live
property evaluation:

- fugacity: `1`;
- component balance: maximum declared feed/reflux/reference flow magnitude;
- energy balance: maximum feed/duty/reference-flow-times-enthalpy magnitude;
- Francis: corresponding positive reference liquid flow;
- terminal amount: corresponding target amount.

The canonical scale vector is reused unchanged for every perturbation and
Jacobian evaluation.

## Fixed Numerical States

Exactly two states are audited:

1. canonical role-mapped seed;
2. deterministic combined bounded perturbation defined in
   `energy_owned_vapor_numerical_gate_v1.audit_points`.

No state may be added, removed, or changed after evaluation.

## Fixed Jacobian Rules

Each state uses an uncolored central-difference Jacobian at:

```text
h   = 1.0e-5
h/2 = 5.0e-6
```

Numerical-coupling tolerance is `1.0e-7`. Rank uses the standard SVD
tolerance:

```text
max(shape) * eps * largest_singular_value
```

The fixed condition-number hard stop is `1.0e8`.

## Acceptance Gate

Both states at both Jacobian steps must have:

- numerical rank `37/37`;
- condition `<1.0e8`;
- no zero row or column;
- no coupling outside the DD-083 structural graph;
- finite live properties and residuals;
- positive temperatures, amounts, liquid flows, and vapor flows;
- valid normalized positive compositions;
- component telescoping `<1.0e-12` relative;
- energy telescoping `<1.0e-10` relative;
- physical liquid height below tray spacing;
- no clipping, projection, property fallback, profile forcing, controller,
  limiter, nonlinear solve, or dynamic integration.

The residual norm is diagnostic, not a pass criterion, because DD-084 tests
numerical readiness rather than root existence.

## Hard Stop

Any failed criterion stops this architecture before a root campaign. Do not
change scales, finite-difference steps, property package, operating
specifications, seed mapping, geometry, or tolerance after the result.

If DD-084 passes, it authorizes drafting and precommitting one bounded
steady-root campaign. It does not itself authorize execution of that solve or
any dynamic model.
