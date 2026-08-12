# Core V3 Dynamic Accuracy Policy

## Decision

Future Core V3 moving-step and trajectory contracts shall assess inventory
refinement on declared physical scales. The maximum coarse/refined difference
divided by each component's initial inventory remains a reported diagnostic,
but it is no longer a standalone acceptance gate.

This change is prospective. It does not reclassify DD-173 or DD-175, alter
their artifacts, or authorize their rerun.

## Reason

The old metric was:

```text
max(abs(N_coarse - N_refined) / N_initial)
```

It has no lower scale. A negligible absolute difference in a trace component
can therefore dominate the entire campaign. DD-173 and DD-175 demonstrated
this behavior while all conservation, physicality, response, and physically
scaled refinement checks passed.

Reducing the DD-173 timestep by four reduced the disputed metric by `12.99x`,
the maximum absolute difference by `12.92x`, and the L1 difference by
`12.87x`. This supports numerical refinement rather than a solver floor.

## Required Hard Gates

Each contract must declare its limits before execution. The first
seven-volume policy retains the limits frozen before DD-174 and DD-175:

| Metric | Limit |
|---|---:|
| Maximum absolute component difference | `<1.0e-4 lbmol` |
| Maximum difference relative to `max(initial component, 1 lbmol)` | `<1.0e-5` |
| Maximum difference relative to initial volume holdup | `<1.0e-6` |
| Component-difference L1 | `<2.0e-4 lbmol` |
| Absolute signed total-inventory difference | `<1.0e-9 lbmol` |

These inventory gates supplement rather than replace:

- same-horizon coarse/refined comparison;
- nonlinear closure, rank, and conditioning;
- equilibrium and physicality;
- exact discrete kinematics;
- global component and energy conservation;
- expected disturbance direction and detectable response;
- provider ownership and fallback prohibition;
- rate-coordinate and algebraic refinement;
- call and wall-clock limits.

## Diagnostic Metric

The unfloored component-relative maximum must still be logged with its volume
and component index. It may trigger engineering review, but it cannot fail a
campaign unless a contract separately justifies that component-specific
relative scale before execution.

## Implementation

`physical_refinement_policy_v1.py` provides a topology-neutral assessment for
any positive volume-by-component inventory matrix. Historical DD-173 and
DD-175 executables remain unchanged. New moving-step and trajectory tools
must use this module rather than reproducing ad hoc refinement formulas.

## Authorization Boundary

Under this corrected prospective policy, DD-175 supplies sufficient evidence
to draft one new short open-loop trajectory contract using `0.25 s` and
`0.125 s` grids. That would be a new accuracy-policy campaign, not a DD-175
retry. Execution remains separately gated and controllers remain excluded.
