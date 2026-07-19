# DD-088 Saturated-Liquid Steady-Root Contract

## Purpose

DD-088 performs exactly one bounded three-start steady-root campaign for the
unchanged DD-087 solved-duty saturated-liquid `40 x 40` system.

The campaign tests whether a common phase-stable physical root exists. It
does not alter the equations, ownership, pressure, geometry, feed, reflux,
reboiler duty, property package, residual scales, or condenser phase model.

No full-system residual or solve may run until the implementation, tests,
exact vectors, transformed bounds, settings, and generated JSON contract are
committed and pushed.

## Unchanged Model

DD-088 retains:

- prescribed five-volume pressure;
- prescribed feed, reflux, and reboiler duty;
- solved condenser duty;
- saturated-liquid drum bubble equations;
- four energy-owned vapor links;
- full fugacity equilibrium at four column vapor outlets;
- Francis-only liquid hydraulics;
- solved distillate and bottoms rates;
- specified terminal liquid amounts.

No profile, previous-step flow, cap, relaxation, limiter, controller,
clipping, projection, or property fallback is permitted.

## Solver

The full campaign uses:

```text
scipy.optimize.least_squares
method   = trf
ftol     = 1e-12
xtol     = 1e-12
gtol     = 1e-12
max_nfev = 500
x_scale  = 1.0
```

The uncolored central-difference Jacobian uses `h=1e-5`. Endpoint audits use
`h=1e-5` and `h/2=5e-6`.

No alternate solver, continuation, restart, adaptive scaling, or analytic
Jacobian may be substituted after execution.

## Frozen Starts

### Canonical

The first vector is the exact committed DD-087 canonical saturated-liquid
vector.

### Deterministic perturbation

The second vector is the exact committed DD-087 deterministic combined
perturbation.

### Independent smooth phase-stable seed

The third vector is constructed before execution without a column-balance
solve:

1. extrapolate the upper-column liquid ALR trend from the role-selected
   rectifying and feed compositions;
2. define an independent drum liquid composition as a fixed `50%` ALR blend
   between the canonical drum and that extrapolated upper-column endpoint;
3. interpolate a smooth ALR liquid profile from that drum composition to the
   role-selected bottom composition;
4. solve the local drum bubble temperature and incipient vapor composition;
5. interpolate a monotonic temperature profile from that bubble temperature
   to the role-selected bottom temperature;
6. initialize column vapor compositions from imposed-phase fugacity ratios;
7. use geometric-mean positive liquid and vapor flow references;
8. split total feed equally into positive initial distillate and bottoms
   rates;
9. reconstruct condenser duty from the drum energy equation.

It may not use a partial full-column solve, balance back-calculation, the
DD-085 root, continuation, or a previous DD-088 endpoint.

The exact resulting vector and construction diagnostics are stored in the
generated JSON contract.

## Bounds

Temperatures:

```text
110 F <= T[j] <= 260 F
```

Liquid amounts:

```text
terminal: 0.8 * target <= NL <= 1.2 * target
interior: 0.2 * reference <= NL <= 2.0 * reference
```

Every liquid, column-vapor, and bubble-vapor composition uses an ALR domain
derived from a `1e-10` simplex floor.

Internal flows:

```text
0.1 * reference <= L,V <= 5.0 * reference
```

Products, for total feed `F`:

```text
1e-4 * F <= D,B <= 1.05 * F
```

Condenser duty:

```text
-3.0 * abs(Q_C,ref) <= Q_C <= -0.1 * abs(Q_C,ref)
```

The duty interval is converted once into the signed affine DD-087
coordinate. An endpoint within `1e-6` transformed-coordinate units of any
bound fails.

## Acceptance

Every start must:

- report successful solver termination;
- reach scaled residual infinity norm below `1e-8`;
- retain rank `40/40` and condition below `1e8` at both endpoint steps;
- retain local bubble rank `3/3` with no zero row or column;
- have no zero full row/column or off-registry numerical coupling;
- telescope component balances below `1e-12` relative;
- telescope energy balances below `1e-10` relative;
- retain positive amounts, products, and internal flows;
- retain finite live properties and normalized compositions above `1e-10`;
- retain monotonic bottomward temperature, including drum temperature below
  the supplying rectifying stage;
- retain negative condenser duty;
- retain liquid heights below tray spacing;
- remain away from all bounds;
- use no clipping, projection, fallback, limiter, controller, or profile
  forcing.

The direct condenser bubble residual must be below `1e-8`. The independent TP
diagnostic retains the DD-087 consistency-floor checks:

```text
abs(sum(x*K)-1) <= 1e-4
beta             <= 1e-3
max|y_bubble-normalize(K*x)| <= 1e-5
```

Stable vapor fails.

All three endpoints must agree in physical variables below `1e-7` using the
precommitted physical scale vector.

## Reporting

For each start, report:

- termination, evaluations, property calls, and wall time;
- initial/final residual block norms;
- movement by coordinate family;
- final duty, product flows, internal flows, temperatures, and compositions;
- bubble composition and TP diagnostic;
- liquid heights and residence times;
- endpoint ranks, conditions, and bound distances;
- component and energy closure.

The result shall compare the accepted or rejected endpoint against DD-085
diagnostically.

## Hard Stop

Any failed start, residual floor, distinct root, active bound, rank loss,
condition failure, positive duty, stable-vapor drum, hot drum, bubble failure,
conservation failure, property failure, clipping, projection, or fallback
retires this five-volume solved-duty saturated-liquid architecture.

Failure must not produce solver tuning, wider bounds, a duty sweep, a partial
condenser, another steady campaign, or dynamics.

A pass authorizes only a structural dynamic-DAE mass-matrix, index, and
consistent-initialization contract. It does not authorize integration.
