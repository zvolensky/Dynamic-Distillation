# DD-085 Frozen Energy-Owned Steady-Root Campaign

## Decision

DD-084 passed its frozen live numerical gate. DD-085 is therefore authorized as
one fixed, bounded, three-start nonlinear root campaign for the unchanged
energy-owned five-volume system.

This document freezes the campaign before execution. A result may be recorded
later without changing this contract.

## Unchanged system

DD-085 uses the exact DD-084:

- `37 x 37` residual and coordinate transforms;
- prescribed pressure profile, feed, reflux, duties, and terminal amounts;
- DWSIM Peng-Robinson property basis;
- full component fugacity equations;
- Francis geometry and coefficients;
- residual scales and structural dependency graph.

No equation, operating parameter, scale, geometry, or property basis may change.

## Solver

The only authorized solver is `scipy.optimize.least_squares` with:

```text
method = trf
jacobian = uncolored central finite difference
jacobian step = 1.0e-5
ftol = 1.0e-12
xtol = 1.0e-12
gtol = 1.0e-12
max_nfev = 500
x_scale = 1.0
```

Endpoint Jacobians are audited at `1.0e-5` and `5.0e-6`.

No alternate solver, continuation, restart, adaptive coordinate scaling, or
post-execution setting change is permitted.

## Frozen starts

The exact numeric vectors are written to the pre-execution contract artifact.

1. The exact DD-084 canonical role-mapped coordinate vector.
2. The exact DD-084 deterministic combined perturbation.
3. An independent smooth physical seed built before execution.

The third seed uses linear terminal-to-terminal temperature interpolation,
linear interpolation in additive-log-ratio liquid-composition coordinates,
declared terminal amounts, one positive geometric-mean interior amount, one
live DWSIM fugacity-ratio estimate for each vapor composition, geometric-mean
reference-order liquid and vapor magnitudes, and an equal total-feed product
split. It uses no nonlinear solve, balance back-calculation, continuation,
DD-082 endpoint, or acceptance truth from the workbook.

## Physical bounds

Bounds are defined in physical space and converted once:

- temperature: `110 <= T <= 260 F`;
- terminal amounts: `0.8` to `1.2` times their targets;
- interior amounts: `0.2` to `2.0` times their references;
- every liquid and vapor mole fraction: floor `1.0e-10`, represented by
  simplex-derived ALR limits and checked again at the endpoint;
- all internal liquid and vapor flows: `0.1` to `5.0` times reference;
- each product flow: `1.0e-4 F` to `1.05 F`.

Any endpoint within `1.0e-6` transformed-coordinate units of a bound fails.

The originally proposed `120 F` lower temperature bound was corrected before
precommit because the exact DD-084 canonical reflux-drum seed is `117.932 F`.
Keeping both `120 F` and the exact canonical start would make the frozen
bounded campaign impossible. `110 F` retains a finite, process-relevant bound
without projecting or altering the audited start.

## Acceptance

Every start must satisfy all of the following:

- scaled residual infinity norm below `1.0e-8`;
- numerical rank `37/37` at both endpoint Jacobian steps;
- Jacobian condition below `1.0e8`;
- no zero rows, zero columns, or unexpected couplings;
- component telescoping relative error below `1.0e-12`;
- energy telescoping relative error below `1.0e-10`;
- finite, positive amounts, flows, and normalized compositions;
- strictly increasing finite temperature profile;
- hydraulic liquid heights below tray spacing;
- no clipping, projection, or property fallback;
- no active transformed-coordinate bound.

All three endpoints must agree in physical variables below `1.0e-7` using the
frozen physical comparison scales.

## Hard stop

Any failed start, distinct root, active bound, rank loss, condition failure,
property failure, nonphysical endpoint, or post-execution contract change
retires this five-volume energy-owned steady architecture.

There will be no DD-086 solver tuning, continuation, wider bounds, or operating
parameter campaign.

## Authorization

A pass authorizes only drafting the structural dynamic DAE contract: conserved
`N/U` differential states, algebraic saturation/hydraulic/vapor-flow
constraints, mass matrix, DAE index, and consistent-initialization conditions.
It does not authorize dynamic integration.
