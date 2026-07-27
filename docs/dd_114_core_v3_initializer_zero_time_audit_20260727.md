# DD-114 Core V3 Initializer Zero-Time Audit Result

- Classification: `dd114_passed`
- Decision: `authorize_frozen_first_step_refinement_contract`
- Constraint infinity norm: `2.018915e-12`
- Provider calls: `6021`
- Wall clock: `7.395 s`
- Nonlinear solve, timestep, or dynamics: `False`

## Decision

The canonical DD-113 endpoint passes the complete live Core V3 zero-time
audit. All 52 DAE, global conservation, and terminal ownership constraints
close below `2.02e-12`. The endpoint is positive, pressure ordered,
conservative, provider compliant, and exactly reproducible from its saved
65-coordinate vector.

This is acceptance as a consistent dynamic initial condition, not as a steady
state. Its component and energy rates are generally nonzero; those rates are
the equation-consistent time derivatives from which a future implicit first
step may begin.

One separately frozen first-step refinement contract is authorized. No
timestep, trajectory, controller, or dynamic integration occurred in DD-114.

## Numerical Gates

| Gate | Result |
|---|---:|
| Constraint infinity norm | `2.018915e-12` |
| Colored Jacobian rank, `h=1e-5` | `52/52` |
| Colored Jacobian rank, `h=5e-6` | `52/52` |
| Full Jacobian rank, `h=1e-5` | `52/52` |
| Worst condition number | `2.054318e3` |
| Two-step spectrum change | `2.906854e-6` |
| Colored/full matrix difference | `0` |
| Zero rows / columns | `0 / 0` |
| Unexpected couplings | `0` |
| Component conservation error | `5.729721e-16` |
| Energy conservation error | `1.702414e-17` |
| Saved physical reproduction | Exact |
| Provider calls | `6021` of `50000` |
| Wall clock | `7.395 s` of `180 s` |

## Canonical State

- Pressure, top to bottom: `218.4400`, `218.4926`, `218.5693`, `218.6389`,
  `218.6595 psia`.
- Temperature, top to bottom: `130.1423`, `152.3682`, `172.5553`,
  `185.4673`, `203.9444 F`.
- Liquid flows through the three hydraulic volumes: `5657.60`, `12710.76`,
  `12689.26 lbmol/h`.
- Vapor flows through the four links: `7305.45`, `7514.80`, `7758.60`,
  `8185.43 lbmol/h`.
- Distillate / bottoms: `2085.67 / 5057.31 lbmol/h`.
- Condenser duty: `-53.24227 MMBTU/h`.

## Provenance

- Frozen contract commit: `6e5538b`.
- Direct DWSIM PR property ownership passed with no fallback or violation.
- Nonlinear solves, initializer executions, timesteps, and dynamic calls: `0`.
