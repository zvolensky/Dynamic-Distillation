# DD-115 Core V3 Initializer First-Step Refinement Result

## Decision

- Classification: `dd115_failed`
- Decision: `stop_initializer_dynamic_handoff`
- Contract commit: `28ba8d9`
- Wall clock: `12.034 s`
- Provider calls: `26,489`
- Retry, controller, changed grid, or longer trajectory: `False`

DD-115 is a formal failure under its precommitted contract. The accepted
DD-114 state is therefore not authorized for a short trajectory, and this
campaign must not be retried by changing timesteps, tolerances, scales, or
solver options.

## What Passed

All three backward-Euler solves converged without retry. Their maximum scaled
residual was `2.734e-13`. Every endpoint Jacobian retained rank `46/46`; the
worst condition number was `7.442e5`, and the two finite-difference spectra
changed by only `1.878e-4`. There were no zero rows, zero columns, unexpected
couplings, property fallbacks, pressure-order violations, nonphysical states,
or conservation failures. Exact discrete component and energy kinematics also
passed.

Most coarse-versus-refined physical comparisons passed:

| Quantity | Result | Limit | Gate |
|---|---:|---:|---|
| Inventory, scaled | `8.124e-5` | `<1e-4` | Pass |
| Lower energy, scaled | `1.909e-5` | `<1e-4` | Pass |
| Top energy, scaled | `9.719e-7` | `<1e-4` | Pass |
| Pressure | `6.468e-4 psia` | `<0.01 psia` | Pass |
| Temperature | `2.330e-3 F` | `<0.01 F` | Pass |
| Liquid flow, normalized | `5.305e-5` | `<1e-3` | Pass |

## What Failed

| Quantity | Result | Limit | Gate |
|---|---:|---:|---|
| Algebraic coordinates | `3.200e-3` | `<1e-3` | Fail |
| Vapor flow, normalized | `2.079e-3` | `<1e-3` | Fail |
| Coarse component-rate consistency | `2.524e-2` | `<1e-3` | Fail |
| Half-step component-rate consistency | `2.394e-2` | `<1e-3` | Fail |
| Coarse energy-rate consistency | `1.852e-2` | `<1e-3` | Fail |
| Half-step energy-rate consistency | `1.739e-2` | `<1e-3` | Fail |

The largest coarse/refined algebraic difference belongs to the generic
`V[stripping_tray->feed_tray]` link. Its corresponding vapor-flow difference
is `26.17 lbmol/h`. The largest zero-time-to-first-step rate changes are in
the bottom volume: methanol changes from `-404.10` to `-705.40 lbmol/h` over
the first half-step, and the energy rate changes from `-1.146` to
`-2.102 MMBTU/h`.

## Interpretation

This is not a nonlinear-solver failure, rank defect, conservation defect, or
property-provider failure. The pressure-consistent initializer reduced the
earlier DD-105 handoff discrepancies dramatically: inventory refinement fell
from `6.28e-2` to `8.12e-5`, algebraic separation from `1.67` to `3.20e-3`,
and pressure separation from `2.77 psi` to `6.47e-4 psi`. The remaining miss
is a finite, localized rate and vapor-traffic transient at the lower boundary
and adjacent vapor link.

The DD-115 gate deliberately required the first endpoint rates to remain
within `0.1%` of the DD-114 zero-time rates and the two grids to agree within
their fixed limits. Those conditions were not met. Core V3 remains a
full-rank, conservative physical equation system, but this initializer-to-step
handoff is retired. Any successor must be a newly justified architecture or
initial-state selection criterion, not a DD-115 timestep or tolerance sweep.

## Evidence

- Frozen contract: `docs/dd_115_core_v3_initializer_first_step_refinement_contract_20260727.md`
- Contract data: `logs/dd115_core_v3_initializer_first_step_refinement_contract_20260727.json`
- Result data: `logs/dd115_core_v3_initializer_first_step_refinement_20260727.json`
- Step kernel: `src/dynamic_distillation/core_v3/conserved_nu_implicit_step_v1.py`
- Runner: `tools/run_core_v3_initializer_first_step_refinement.py`
