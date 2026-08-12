# DD-175 Seven-Volume Smaller Moving-Step Contract

## Purpose

DD-174 established that DD-173's saved endpoints are close on physical
inventory scales while preserving DD-173's formal failure. DD-175 tests
whether reducing the timestep produces the expected convergence and satisfies
the original strict refinement gate without relaxing it.

## Frozen Experiment

- initial state: accepted DD-169 seven-volume stationary root;
- disturbance: unchanged DD-173 `+0.1%` increase in every feed component flow
  and total feed enthalpy, preserving composition and specific enthalpy;
- full path: one `0.25 s` backward-Euler step;
- refined path: two successive `0.125 s` backward-Euler steps;
- solver, colored Jacobian, scaling, provider ownership, and exact unrounded
  memoization: unchanged from DD-173;
- controllers: none;
- retries, alternate timesteps, alternate disturbances, and trajectories:
  prohibited.

## Gates

All DD-173 root, rank, condition, equilibrium, conservation, kinematic,
physicality, response, provider, call, and wall gates remain in force. The
original maximum relative component-inventory refinement limit remains
`<1e-7`, with rate and algebraic refinement below `1e-5` and total-inventory
refinement below `1e-6 lbmol`.

The DD-174 physical limits also remain in force: maximum absolute component
difference `<1e-4 lbmol`, state-floor-relative difference `<1e-5`,
volume-holdup-relative difference `<1e-6`, component L1 difference
`<2e-4 lbmol`, and absolute signed total difference `<1e-9 lbmol`.

## Decision

A complete pass authorizes only one separately frozen short open-loop
trajectory contract on the smaller grid. Any failed gate stops before a
trajectory, with no DD-175 rerun or tuning.
