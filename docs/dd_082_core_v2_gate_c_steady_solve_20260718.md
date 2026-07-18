# DD-082 Core V2 Gate C Steady-Root Decision

## Purpose

DD-082 executes the one fixed three-start campaign frozen in commit
`dbd4c57`. It uses the unchanged DD-081 `38 x 38` live DWSIM PR residual,
fixed scales, transformed-coordinate bounds, colored central-difference
Jacobian, and trust-region solver.

No continuation, alternate solver, regularization, geometry change, Francis
coefficient change, fallback, clipping, or post-result tuning was attempted.

## Result

DD-082 fails the Gate C steady-root acceptance gate.

All three starts terminate successfully according to the trust-region solver
and converge to essentially the same bounded endpoint:

| Start | Scaled residual infinity norm | Function/Jacobian evaluations | Accepted |
|---|---:|---:|---|
| canonical mini8-derived | `9.15999e-3` | `24 / 23` | No |
| deterministic bounded perturbation | `9.15999e-3` | `30 / 29` | No |
| independent smooth profile | `9.15999e-3` | `36 / 33` | No |

Maximum pairwise normalized physical-root disagreement is `2.12e-9`, well
inside the `1e-7` agreement target. The failure is therefore not
initial-guess dependence.

The common endpoint remains:

- numerical rank `38/38` at both Jacobian steps;
- condition approximately `1.92e4`;
- conservative to DD-081 precision;
- finite and positive;
- below tray-spacing limits;
- free of clipping, projection, and property fallback.

However:

- the residual floor is about `9.16e-3`, not below `1e-8`;
- `N[reflux_drum,n-Pentane]` is active at its upper transformed bound;
- the upper bound is `50x` the tiny reference inventory;
- an accepted root may not depend on an active coordinate bound.

## Common Endpoint

Representative canonical-start endpoint:

| Quantity | Result |
|---|---:|
| Distillate | `2303.31 lbmol/h` |
| Bottoms | `4723.94 lbmol/h` |
| Temperatures | `162.15, 176.11, 179.48, 188.90, 200.44 F` |
| Liquid amounts | `1388.90, 32.23, 45.41, 53.95, 794.00 lbmol` |
| Francis flows | `5924.80, 12763.51, 12761.23 lbmol/h` |
| Hydraulic residence times | `19.59, 12.81, 15.22 s` |

The endpoint reconciles most energy, equilibrium, hydraulic, and terminal
inventory equations. The remaining floor is dominated by component balances:

| Residual | Raw | Scaled |
|---|---:|---:|
| reflux-drum n-pentane balance | `76.3345 lbmol/h` | `9.15999e-3` |
| rectifying-tray n-pentane balance | `30.4309 lbmol/h` | `3.65165e-3` |
| feed-tray n-pentane balance | `8.9693 lbmol/h` | `1.07629e-3` |
| stripping-tray n-pentane balance | `3.3382 lbmol/h` | `4.00577e-4` |

The largest energy-balance remainder is only `5763.54 BTU/h`, scaled
`1.05355e-4`. Local energy reconstruction, equilibrium, Francis, and terminal
inventory residuals are much smaller.

## Interpretation

The three starts finding the same endpoint is useful evidence: the campaign
is reproducible and the numerical formulation is not losing rank. The active
drum n-pentane bound and shared component-balance floor show that this bounded
operating specification did not demonstrate a common physical root.

This result does not mathematically prove that no root exists outside the
predeclared coordinate box. Testing a wider box would be a new campaign and
is prohibited by the DD-082 hard stop.

## Evidence

- Frozen campaign: commit `dbd4c57`
- DD-081 snapshot: commit `892bfe2`
- `logs/dd082_core_v2_gate_c_steady_solve_20260718.json`
- `logs/dd082_core_v2_gate_c_steady_solve_20260718.md`
- `docs/dd_082_gate_c_steady_solve_contract_20260718.md`

## Decision

Gate C fails.

Do not create a DD-083 solver-tuning, continuation, wider-bound, geometry, or
alternate operating-specification variant. The current prescribed-pressure,
prescribed-vapor five-volume operating specification is retired. Gates D-G,
the five-volume dynamic test, and production scaling remain unauthorized.

