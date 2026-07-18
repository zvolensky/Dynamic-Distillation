# DD-079 Core V2 Gate A Dynamic Response

## Purpose

DD-079 asks one bounded question:

> Does time integration of the v2 property-free source assembly reproduce the
> independently implemented Skogestad model under identical states,
> disturbances, output grids, and solver tolerances?

It completes Gate A before energy or live thermodynamics are introduced.

## Fixed Scope

- binary constant-relative-volatility source model;
- material balances and linear liquid-holdup response only;
- prescribed vapor traffic;
- `500 min` horizon with `1 min` comparison output;
- BDF primary integration at `rtol=1e-10`, `atol=1e-12`;
- Radau refinement at `rtol=2e-11`, `atol=2e-13`;
- exact piecewise disturbance segmentation;
- no nonlinear algebraic solve.

The following were excluded:

- DWSIM or other property calls;
- energy equations;
- controllers;
- mini8 equations or historical trajectories;
- explicit Euler as an acceptance integrator;
- clipping, projection, profile substitution, or accepted holdup floors.

## Dynamic Cases

### Nominal profile drift

The published tabulated state was integrated without disturbance. DD-078
showed that it has a small nonzero source residual, so the expected trajectory
contains the same small drift in both implementations. No state was snapped
back to the published profile.

### Published feed disturbance

The accepted immediate step was applied:

```text
F: 1.00 -> 1.01 kmol/min at t=0
```

The integration harness also has a regression test with a nonzero event at
`t=5 min`; the pre-event segment closes exactly and the post-event total
inventory accumulation is `0.01 kmol/min`.

### Bounded perturbed state

The deterministic DD-078 composition and holdup perturbations were integrated
under the nominal source equations. DD-078's separate aggressive parameter
perturbation was not carried into dynamics because it drains the bottom
holdup below zero. No floor or clipping was introduced to hide that result.

## Results

| Case | V2/reference normalized maximum | BDF/Radau normalized maximum | Total closure | Light closure |
|---|---:|---:|---:|---:|
| Nominal drift | `3.851e-11` | `1.362e-10` | `0` | `1.363e-15` |
| +1% feed | `4.970e-13` | `1.392e-9` | `2.426e-15` | `2.764e-12` |
| Perturbed state | `3.673e-13` | `1.600e-9` | `2.079e-15` | `7.300e-13` |

All cases:

- completed the full `500 min`;
- stayed within `0 <= x <= 1`;
- retained positive liquid holdup;
- used no safeguard;
- passed trajectory parity below `1e-9`;
- passed integrator refinement below `1e-7`;
- passed solver-integrated conservation below `1e-10`;
- withdrew terminal components as `D*x_top(t)` and `B*x_bottom(t)`.

The saved `1 min` grid's independent trapezoidal balance diagnostic is
intentionally reported separately. Its worst normalized discrepancy is
`1.238e-6`, while the solver-integrated external balance closes below
`2.764e-12`. This distinction prevents output-grid quadrature error from being
misreported as a differential-equation or solver conservation defect.

## Evidence

- `src/dynamic_distillation/core_v2/source_equation_dynamics_v1.py`
- `tools/audit_core_v2_gate_a_dynamics.py`
- `tests/test_core_v2_source_equation_dynamics_v1.py`
- `logs/dd079_core_v2_gate_a_dynamics_20260718.json`
- `logs/dd079_core_v2_gate_a_dynamics_20260718.md`
- `logs/dd079_core_v2_gate_a_dynamics_20260718_profiles.csv`

## Decision

DD-079 passes. Gate A is complete.

Gate B is authorized for one representative mini8 inventory volume with:

- prescribed pressure;
- conserved component inventory and internal energy;
- live DWSIM property evaluation;
- algebraic temperature and phase-equilibrium reconstruction;
- predefined perturbations, rank, conservation, and dynamic gates.

This does not authorize the five-volume Gate C solve, energy-determined vapor
traffic, a pressure-drop network, explicit vapor inventory, or production
integration.
