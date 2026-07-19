# DD-087 Saturated-Liquid Condenser Numerical Audit

## Decision

DD-087 passes.

The solved-duty, saturated-liquid total-condenser architecture remains
finite, conservative, full rank, physically bounded, and acceptably
conditioned when translated into the live DWSIM PR `40 x 40` residual.

This result authorizes drafting and precommitting one bounded `40 x 40`
steady-root campaign. It does not authorize executing that solve before
precommit, dynamic integration, pressure dynamics, vapor holdup, controllers,
or production scaling.

## Frozen Execution

The audit contract and exact vectors were committed as `69101d1` before the
first full residual evaluation.

The execution used:

- canonical saturated-liquid seed;
- one deterministic combined perturbation;
- fixed 40-element residual-scale vector;
- uncolored central differences at `1.0e-5` and `5.0e-6`;
- live DWSIM PR phase fugacity, enthalpy, density, and TP flash;
- no full nonlinear solve or dynamic integration.

The one authorized execution completed in `7.155 s`.

## Canonical Condenser Boundary

`ThermoProviderV1` has no direct fixed-`(P,x)` DWSIM bubble API. The permitted
local `3 x 3` fugacity seed solve produced:

```text
T_D,bubble = 117.816384892 F
y_bubble   = [0.958689151, 0.041309552, 0.000001297]
residual infinity norm = 2.55e-15
```

The condenser energy seed then gave:

```text
Q_C,ref = -55,003,568.309 BTU/h
s_Q     =  55,003,568.309 BTU/h
```

The negative duty is represented with the frozen signed affine coordinate:

```text
Q_C = Q_C,ref + s_Q * q_Q_C
```

## Phase Diagnostic

The independent DWSIM TP flash at the exact forced-phase fugacity solution
reported:

```text
sum(x*K)-1                         = 1.46785e-5
Rachford-Rice vapor fraction       = 4.45938e-4
max|y_bubble - normalize(K*x)|     = 1.21906e-6
```

This is a near-bubble two-phase classification, not the stable-vapor state
found in DD-085. It passes the precommitted cross-API tolerances.

Preparation also established that the TP-flash endpoint and imposed-phase
fugacity endpoint have a small provider consistency floor: forcing the TP
criterion more tightly leaves a direct fugacity residual near `1.41e-4`.
DD-087 therefore keeps the direct bubble equations as the primary strict
condition and uses TP flash as an independent phase-region check.

## Numerical Results

| State | Step | Full rank | Condition | Bubble rank |
|---|---:|---:|---:|---:|
| Canonical | `1.0e-5` | `40/40` | `2.44731e6` | `3/3` |
| Canonical | `5.0e-6` | `40/40` | `2.29944e6` | `3/3` |
| Perturbed | `1.0e-5` | `40/40` | `2.44243e6` | `3/3` |
| Perturbed | `5.0e-6` | `40/40` | `2.44242e6` | `3/3` |

All four Jacobians have:

- no zero row or column;
- no numerical coupling outside the DD-086 registry;
- no local bubble zero row or column;
- stable rank at both finite-difference steps.

The smallest local bubble singular value is approximately `0.447`, so the
added saturation condition is independent rather than a numerical duplicate
of the two vapor-composition relations.

## Conservation and Ownership

The maximum reported relative errors are:

```text
component telescoping = 1.79e-16
energy telescoping    = 3.05e-16
```

The structural and numerical ownership checks confirm:

- `Q_C` is an unknown, not a fixed external parameter;
- `Q_C` appears only in `energy_balance[reflux_drum]`;
- the solved duty is included in whole-system energy telescoping;
- all bubble coordinates and drum temperature retain their declared
  fugacity couplings;
- no profile, controller, limiter, clipping, projection, or property fallback
  is active.

## Physical Gate

Both states retain:

- positive amounts and internal flows;
- positive normalized liquid, column-vapor, and bubble-vapor compositions;
- negative condenser duty;
- finite enthalpies, densities, fugacity coefficients, and residuals;
- liquid heights below the `1.5 ft` tray spacing.

The maximum audited liquid height is `0.659 ft`.

## Residual Context

The canonical scaled residual infinity norm is `0.397863`; the perturbed
value is `0.389121`. The dominant rows remain the stripping/feed Francis
hydraulic equations, followed by the drum propane component balance and an
interior fugacity row.

These residuals are diagnostic and were not a DD-087 acceptance criterion.
DD-087 establishes numerical readiness for a root campaign; it does not
claim that a physical steady root exists.

## Next Authorized Increment

DD-088 may only:

1. define one bounded `40 x 40` steady-root campaign;
2. precommit all starts, bounds, scales, solver settings, physical gates, and
   stop rules;
3. execute only after that separate contract is committed.

No solver tuning, duty sweep, dynamic integration, DAE extension, pressure
release, vapor holdup, or controller work is authorized by DD-087.

Primary evidence:

- `logs/dd087_condenser_saturated_liquid_numerical_contract_20260718.json`
- `logs/dd087_condenser_saturated_liquid_numerical_20260718.json`
