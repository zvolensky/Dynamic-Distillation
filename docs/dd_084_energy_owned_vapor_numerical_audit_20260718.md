# DD-084 Energy-Owned Vapor Numerical Audit

## Purpose

DD-084 evaluates the DD-083 `37 x 37` energy-owned vapor-flow residual with
live DWSIM PR properties and audits its numerical Jacobian before any
nonlinear solve.

The complete campaign was frozen and pushed in commit `e4aea9d` before the
first live evaluation. No setting, state, scale, tolerance, or equation was
changed after seeing the result.

## Result

DD-084 passes its numerical gate on the first authorized execution.

| State | Scaled residual infinity norm | Rank at `h` / `h/2` | Worst condition |
|---|---:|---:|---:|
| canonical role-mapped seed | `0.397863` | `37 / 37` | `1.78028e6` |
| deterministic combined perturbation | `0.389121` | `37 / 37` | `1.77618e6` |

For both states and both finite-difference steps:

- numerical rank is `37/37`;
- condition is below the frozen `1e8` hard stop;
- no residual row or coordinate column is numerically zero;
- no numerical coupling appears outside the DD-083 structural graph;
- all live properties and residuals are finite;
- amounts, compositions, temperatures, and flows remain physical;
- liquid heights remain below tray spacing;
- no clipping, projection, property fallback, profile forcing, controller,
  limiter, nonlinear solve, or dynamic integration is present.

## Conservation

The simultaneous four-vapor-link assembly telescopes at roundoff:

| State | Component relative error | Energy relative error |
|---|---:|---:|
| canonical | `1.79e-16` | `1.70e-16` |
| deterministic perturbation | `6.45e-17` | `2.55e-16` |

This confirms that releasing each vapor interface independently did not
duplicate or omit an internal material or energy stream.

## Seed Residual

The role-mapped workbook seed is not a steady solution. Its largest scaled
residuals are:

| Residual | Raw | Scaled |
|---|---:|---:|
| stripping-tray Francis equation | `-5007.02 lbmol/h` | `-0.397863` |
| feed-tray Francis equation | `-3737.28 lbmol/h` | `-0.302071` |
| reflux-drum propane balance | `-2405.87 lbmol/h` | `-0.191173` |
| rectifying-tray n-pentane fugacity | `-0.156468` | `-0.156468` |
| reflux-drum n-butane balance | `1781.74 lbmol/h` | `0.141579` |

That residual is diagnostic and was deliberately not a DD-084 pass
criterion. The purpose of this gate was to determine whether the full
fugacity and energy-owned-flow equations are finite, conservative, square,
full rank, and sufficiently conditioned for one bounded root campaign.

The dominant Francis mismatch also confirms that the workbook liquid profile
is not forcing the new model. Live Francis calculations remain the sole
owner of the three tray liquid flows.

## Interpretation

DD-084 answers the main uncertainty left by DD-083:

- the four saturation conditions are numerically independent;
- the four vapor-link coordinates are numerically active;
- the full live residual does not lose rank when DWSIM properties replace
  the structural dependency graph;
- the current seed is meaningfully displaced from the new model's root, but
  the displacement is not a numerical singularity.

This does not prove a physical root exists. DD-082 already showed why that
distinction matters.

## Evidence

- frozen definition: commit `e4aea9d`;
- `logs/dd084_energy_owned_vapor_numerical_20260718.json`;
- `logs/dd084_energy_owned_vapor_numerical_20260718.md`;
- `src/dynamic_distillation/core_v2/energy_owned_vapor_numerical_gate_v1.py`;
- `tools/audit_core_v2_energy_owned_vapor_numerical.py`;
- `tests/test_core_v2_energy_owned_vapor_numerical_gate_v1.py`.

## Decision

DD-084 passes.

The next permitted increment is to draft and precommit exactly one bounded
steady-root campaign for this unchanged `37 x 37` residual. The campaign must
declare its transformed-coordinate bounds, starts, solver, tolerances,
physical acceptance gate, and hard stop before execution.

No nonlinear solve or dynamic integration is authorized by DD-084 itself.
