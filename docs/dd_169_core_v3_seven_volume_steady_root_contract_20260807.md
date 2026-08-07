# DD-169 Frozen Seven-Volume Stationary-Root Contract

## Objective

Determine whether the DD-168 live, full-rank seven-volume Core V3 system has a
reachable and reproducible physical stationary root.

## Frozen Starts

Exactly two complete 56-coordinate starts are permitted:

1. The unsolved DD-168 source-mapped state.
2. A separately constructed smooth topology-scale state using an independent
   ALR composition profile, direct imposed-phase fugacity vapor estimates, a
   local condenser bubble calculation, deterministic positive inventories and
   flows, and direct condenser-energy duty reconstruction.

The starts differ by `3.104241` in transformed-coordinate infinity norm. The
independent start uses no full residual, partial balance solve, continuation,
other-start endpoint, or imported accepted root.

## Frozen Method

- Solver: `scipy.optimize.least_squares(method="trf")`.
- Jacobian: central difference at `1e-5` during solving.
- Endpoint Jacobians: `1e-5` and `5e-6`.
- Maximum function evaluations per start: `500`.
- Residual limit: `<1e-8` scaled infinity norm.
- Full fugacity and condenser bubble blocks: `<1e-10`.
- Physical common-root agreement: `<1e-7`.
- Full endpoint rank: `56` at both finite-difference steps.
- Condenser local rank: `3`.
- Condition limit: `<1e8`.
- Spectrum relative change: `<0.25`.
- Component and energy telescoping: `<1e-12` and `<1e-10`.
- No active transformed bound within `1e-6`.
- Logical provider-call limit: `<500,000`.
- Total wall limit: `<600 s`.

The same physical bounds, residual scales, DWSIM Peng-Robinson provider
ownership, pressure profile, reflux, feed, reboiler duty, terminal amounts,
and hydraulic geometry are used for both starts.

Exact-state, unrounded memoization is enabled and cleared separately for each
start. It may avoid repeated DWSIM delegation but cannot alter a residual,
Jacobian coordinate, solver decision, or acceptance result. Logical calls and
memo statistics are both reported.

## Physical Gates

Every endpoint must have positive inventories, liquid and vapor flows, product
flows, density, compositions, and over-weir head; liquid heights below spacing;
negative condenser duty; ordered pressure and temperature; internally coherent
TP-flash diagnostics; parameter-aligned independent-PR bubble agreement; exact
condenser-duty ownership; and no fallback, clipping, or projection.

## Hard Stop

This contract authorizes one execution after commit. No retry, widened bound,
changed scale, altered tolerance, continuation, alternate solver, projection,
or start replacement is permitted after results are known.

Passing authorizes only a structural seven-volume conserved dynamic-DAE
contract. Failure stops this scale-up path without another root campaign.

No timestep, controller, initializer, mass matrix, or dynamic integration is
authorized by DD-169.

## Frozen Artifact

- `logs/dd169_core_v3_seven_volume_steady_root_contract_20260807.json`
- Contract payload SHA-256:
  `3d29f3ac64a5ff3c9df2941323024d425213fc96053746b238c13ac14967a836`
