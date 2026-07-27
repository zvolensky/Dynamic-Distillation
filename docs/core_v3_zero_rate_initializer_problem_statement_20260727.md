# Core V3 Zero-Rate Initializer Problem Statement

## Purpose

This package requests an independent technical review of a reduced dynamic distillation model and its initialization problem. The immediate question is no longer whether the nonlinear solver can reduce a residual. It is whether the current equations, operating specifications, and terminal inventory ownership admit a physically meaningful state with all conserved rates exactly zero.

The investigation has produced useful structural and numerical evidence, but repeated initializer formulations have not produced an accepted steady initial state. The current path is stopped pending an architectural decision.

## Model Under Review

Core V3 is a generic five-volume reduction of a C3/C4 splitter:

1. Reflux drum.
2. Rectifying tray.
3. Feed tray.
4. Stripping tray.
5. Combined reboiler/sump.

The case has three components: n-propane, n-butane, and n-pentane. The governing model uses:

- conserved component inventories `N` in all five volumes;
- independent internal energy `U` in the four lower volumes;
- derived reflux-drum energy on its saturated-liquid manifold;
- direct DWSIM Peng-Robinson fugacity, enthalpy, density, and vapor-compressibility calls;
- full component fugacity equilibrium;
- Francis-only liquid hydraulics on the three trays;
- energy-owned vapor flows;
- four algebraic vapor pressure-drop equations;
- fixed reflux-drum pressure;
- fixed feed, reflux, distillate, bottoms, and reboiler-duty specifications for this feasibility model;
- solved condenser duty;
- no profile forcing, clipping, flow caps, relaxation, controllers, or property fallback.

The architecture is generic in component count and physical role. No interior source-stage number is embedded in the equations.

## Desired Initialization

The desired initializer would provide a state suitable for implicit dynamic integration and, ideally, a steady state:

```text
dN/dt = 0
dU/dt = 0
all algebraic equilibrium, hydraulic, energy, storage, and pressure equations = 0
```

The original pressure-consistent initializer instead solved for conserved states, rates, and algebraic variables while preserving whole-column component totals, stored energy, and terminal holdups. It produced a live equation-consistent state, but that state had significant nonzero rates. Its first implicit step was physical and conservative but exhibited a real startup transient rather than a clean steady handoff.

## Evidence Sequence

### DD-108 through DD-111: conserved pressure formulation

- The corrected conserved-`N/U` pressure DAE is `46 x 46` and structurally full rank.
- Its live Jacobian is full rank and conservative under direct DWSIM PR evaluation.
- The pressure-consistent initializer contains 65 variables and 52 exact constraints, leaving a 13-dimensional selection manifold.

### DD-112 through DD-114: consistent but non-steady initial state

- Two constrained initializer starts converged to physically near-identical endpoints.
- All 52 live equations and selection constraints closed below approximately `2e-12` in the canonical zero-time audit.
- The endpoint Jacobian was rank `52/52`, condition approximately `2.05e3`, and provider compliant.
- The accepted state was dynamically consistent with its equation-owned nonzero rates. It was not a steady state.

### DD-115 through DD-117: first-step handoff

- One `1.0 s` backward-Euler step and two `0.5 s` steps all converged at machine-precision residuals.
- Inventory, energy, pressure, temperature, and liquid-flow refinement passed.
- Algebraic, vapor-flow, and initial-rate refinement failed.
- Term-level reconstruction showed that the discrepancy was a real physical transient, dominated by the energy-owned bottom-to-stripping vapor link, rather than a balance or equation-ownership coding defect.
- A reporting-contaminated gate was corrected statically without rerunning the numerical evidence.

### DD-118: structural zero-rate audit

Fixing all 19 conserved rates exactly to zero removes them from the unknown vector:

```text
46 DAE rows x 46 state/algebraic unknowns
```

This core is structurally full rank. Retaining all inherited initializer targets gives:

```text
52 rows x 46 unknowns
```

The six surplus targets are:

- three whole-column component inventories;
- one whole-column stored-energy target;
- reflux-drum total holdup;
- reboiler/sump total holdup.

The global component and energy targets were therefore demoted to diagnostics. The two terminal holdups were provisionally retained as physical scale selections.

### DD-119: live zero-rate readiness audit

The corrected residual contained 46 unchanged DAE rows plus the two terminal holdup rows, giving `48 x 46`. It was evaluated at the DD-112 canonical endpoint and the independently advanced DD-115 one-second state.

Results:

- DAE-only formal rank: `46/46` at both states.
- DAE-only condition: `2.54e13` to `3.76e13`.
- Terminal-augmented rank: `46/46`.
- Terminal-augmented condition: `5.62e3` to `5.68e3`.
- Spectrum change: below `4.73e-7`.
- Colored/full Jacobian difference: zero.
- Provider calls: `7,113` in `3.144 s`.

Interpretation: the DAE-only system has two extremely weak terminal inventory scale directions. The two terminal holdup rows regularize those directions by roughly ten orders of magnitude.

### DD-120: terminal-scaled zero-rate root campaign

Exactly two frozen starts were solved with one bounded `scipy.optimize.least_squares(method="trf")` configuration and the unchanged 20-color finite-difference Jacobian.

Both starts:

- reported solver success;
- converged to endpoints differing by only `1.3515e-9` in transformed coordinates;
- satisfied both terminal holdup rows below `7.04e-12` scaled;
- retained full column rank, good conditioning, interior bounds, ordered pressure, physical inventories and flows, exact conservation, and approved provider ownership;
- reached optimality below `5.60e-9`.

However, both stopped at the same DAE residual floor:

```text
scaled residual infinity norm = 2.4485755e-3
least-squares cost            = 2.9442737e-5
left-null residual projection = 7.6736872e-3
required residual limit       = 1.0e-8
```

The residual gate was the only failed gate. DD-120 therefore retired the terminal-scaled zero-rate root path without a retry, changed target, alternate solver, continuation, timestep, or controller.

## Current Interpretation

The strongest supported conclusion is:

> Under the frozen Core V3 equations, operating specifications, scaling, bounds, and inherited drum/sump holdups, the two-start trust-region campaign found a reproducible physical least-squares endpoint but not an exact zero-rate root.

This is strong numerical evidence that the inherited terminal holdups are incompatible with exact zero rate under the present specifications. It is not a formal proof that no root exists anywhere, nor does it prove the full dynamic model is invalid.

The investigation is now encountering diminishing returns because each prospective successor changes which physical quantities are specified rather than merely improving numerical solution quality. Continuing automatically would become a sequence of specification substitutions:

- release terminal holdups;
- add level controls;
- change product or duty ownership;
- introduce pseudo-transient continuation;
- accept nonzero initial rates;
- or choose another terminal inventory gauge.

Those are architectural decisions and should not be disguised as solver tuning.

## Important Evidence Limitation

The DD-120 result preserves both final coordinate vectors, aggregate residual norms, costs, left-null projections, physical endpoint fields, Jacobian spectra, and provider provenance. Its JSON report does not preserve the final 48-element residual vector or a per-row residual ranking. The campaign was not rerun merely to improve reporting. Consequently, this package establishes the aggregate residual floor but does not claim which individual DAE row is the largest contributor.

## Questions for Independent Review

1. Are reflux-drum and reboiler/sump holdups legitimate algebraic scale selections for this zero-rate problem, or should terminal levels remain differential states selected only by initial conditions and controllers?
2. Is the model over-specified by simultaneously fixing feed, reflux, distillate, bottoms, reboiler duty, top pressure, and both terminal holdups?
3. Does the near-rank deficiency of the DAE-only Jacobian represent two true gauge freedoms, or weak but genuine physical ownership through energy/storage equations?
4. Is an exact zero-rate initial state physically necessary, or should acceptance instead require exact DAE consistency with bounded nonzero rates followed by a grid-refined startup transient?
5. Would a DAE-only solve without terminal holdup rows be meaningful, and how should its terminal inventory scales be selected without introducing arbitrary targets?
6. Should terminal level controllers or different manipulated-variable ownership be part of the steady-state equations rather than added only after initialization?
7. Is there an equation or specification mismatch in the terminal energy, product-flow, volume, or pressure ownership that explains the `2.4486e-3` residual floor?
8. What is the smallest decisive follow-up that distinguishes physical infeasibility from numerical ill-conditioning without starting another open-ended solver campaign?

## Requested Reviewer Deliverable

Please provide:

- an independent equation/specification degree-of-freedom assessment;
- a judgment on terminal inventory ownership;
- identification of any duplicated or incompatible equation/specification;
- a recommendation to accept nonzero-rate initialization, redesign terminal ownership, or perform one specifically bounded follow-up;
- explicit stop criteria for any recommended follow-up.

## Reproduction Notes

The repository branch is `architecture/equilibrium-dae-v2`. DD-119 and DD-120 were frozen and executed from committed contracts. The relevant contract/result commits are:

- DD-119 contract: `a56d2ce`.
- DD-119 result: `5499c08`.
- DD-120 contract: `67b9c51`.
- DD-120 result and stop decision: `4c1597f`.

The focused Core V3 suite passed `163` tests before DD-120 execution. The package includes the reduced workbook, source modules, tools, tests, contracts, result JSON, and narrative decision documents needed for code-level review.
