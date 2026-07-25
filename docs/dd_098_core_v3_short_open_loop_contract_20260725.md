# DD-098 Core V3 Short Open-Loop Contract

Date: 2026-07-25

## Purpose

DD-098 is the first Core V3 multi-step and nonzero-motion test. It asks
whether the accepted DD-097 implicit step can advance a short, physically
forced open-loop transient without losing nonlinear convergence, physicality,
conservation, provider ownership, or step refinement.

This remains a reduced five-volume feasibility test. It is not a production
column run, controller test, initializer, or steady-state acceptance test.

## Frozen Initial State

Every trajectory starts independently from the exact accepted DD-094 root.
Pressure, geometry, reflux, reboiler duty, condenser-duty ownership,
distillate rate, bottoms rate, and all DD-097 solver settings remain
unchanged.

## Frozen Experiments

### Root Hold

Run one unchanged-input `2.0 s` trajectory with `dt=1.0 s`. Its two steps
shall preserve the exact steady root without artificial drift.

### Feed Step

At `t=0`, multiply every feed component rate and total feed enthalpy by
exactly `1.001`:

```text
F_k,new = 1.001 * F_k,DD094
H_feed,new = 1.001 * H_feed,DD094
```

This preserves feed composition and specific enthalpy. No other input,
parameter, state, duty, product rate, or property basis changes.

Run two independent `2.0 s` trajectories from DD-094:

- `dt=1.0 s` for two steps;
- `dt=0.5 s` for four steps.

The smaller-step trajectory does not continue from the larger-step endpoint.

## Solver And Step Ownership

Every endpoint uses the unchanged DD-097 unbounded backward-Euler solver:

```text
least_squares(method="trf")
central Jacobian step = 1e-5
ftol = xtol = gtol = 1e-12
max_nfev = 40
x_scale = 1
```

Each accepted endpoint becomes the sole inventory, algebraic initial guess,
and property-state template for the next step. Rate coordinates restart at
zero. A failed step terminates its trajectory immediately. No retry,
substepping, predictor variation, bound, clipping, projection, relaxation,
or property fallback is permitted.

## Per-Step Gates

Every requested step shall complete and satisfy:

- solver success within `40` residual evaluations;
- scaled residual infinity norm below `1e-8`;
- endpoint Jacobian rank `38/38` and condition below `1e8`;
- direct storage bubble residual below `1e-10`;
- global discrete component and energy errors below `1e-8` relative;
- positive finite inventories, compositions, temperatures, and flows;
- strictly increasing temperature from drum to bottom;
- negative condenser duty;
- hydraulic liquid heights below tray spacing;
- DD-090 provider provenance with no fallback.

## Root-Hold Gates

Across the unchanged-input trajectory:

- maximum component rate shall remain below `1e-4 lbmol/h`;
- maximum endpoint inventory drift divided by initial inventory shall remain
  below `2e-9`;
- maximum algebraic-coordinate drift shall remain below `2e-7`.

## Feed-Step Motion And Conservation Gates

With fixed total product rates, the expected total inventory accumulation is:

```text
Delta N_expected =
  (sum(F_new) - D_DD094 - B_DD094) * 2.0 / 3600
```

Each perturbed trajectory shall:

- have strictly increasing total inventory at every endpoint;
- produce maximum absolute component rate above `1e-3 lbmol/h`;
- produce total accumulation above `1e-4 lbmol`;
- match `Delta N_expected` within `1e-6` relative.

These are global conservation consequences, not ChemSep profile targets.

## Refinement Gates

At `t=2.0 s`, the `1.0 s` and `0.5 s` perturbed endpoints shall agree within:

- `1e-5` maximum component-inventory difference normalized by the DD-094
  inventory;
- `1e-4` maximum algebraic-coordinate difference;
- `1e-3 F` maximum temperature difference;
- `1e-6` relative total-accumulation difference.

## Execution Rule

The exact source evidence, implementation, workbook, root, perturbation,
duration, steps, solver, and gates shall be hashed into a generated contract
and committed before one live execution. An existing result artifact
prohibits rerun.

Preparation performs no property evaluation, nonlinear solve, dynamic step,
or trajectory.

## Hard Stop

Any failed requested step or frozen gate stops this trajectory architecture.
Do not reduce the step, shorten the duration, tune the solver, weaken the
perturbation, change a property interface, or add a controller afterward.

## Authorization Boundary

A pass establishes a bounded nonzero Core V3 transient and may authorize one
separately frozen longer open-loop feasibility contract. It does not authorize
controllers, production tray count, pressure dynamics, vapor holdup,
initializer development, or design-point acceptance.
