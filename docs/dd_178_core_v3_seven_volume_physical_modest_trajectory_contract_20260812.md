# DD-178 Seven-Volume Physical-Policy Modest-Trajectory Contract

## Purpose

DD-178 extends the accepted DD-177 trajectory from two to ten simulated
seconds without changing the initial state, disturbance, equations, solver,
property provider, timestep grids, or accuracy policy. It tests whether the
passing behavior persists through 120 successive moving roots.

## Frozen Experiment

- initial state: accepted DD-169 seven-volume stationary root;
- disturbance: unchanged `+0.1%` feed component rates and total feed enthalpy;
- coarse path: `40 x 0.25 s`;
- refined path: `80 x 0.125 s`;
- shared comparisons: all 40 coarse endpoints against refined endpoints at
  the same physical times;
- controllers, clipping, projection, fallback, retry, alternate grid, and
  continuation: prohibited.

## Gates

All DD-177 root, physicality, equilibrium, conservation, kinematic, response,
provider, and physical-refinement gates remain unchanged. Every root must
close below `1e-8`, retain rank `54`, and condition below `1e8`. Both paths
must complete with positive monotone accumulation and global component
identity below `1e-6 lbmol`.

Every shared time must satisfy the DD-176 physical inventory limits and
`<1e-5` rate/algebraic refinement. The unfloored component-relative maximum
remains diagnostic only. Logical calls must remain below `650,000`; wall time
must remain below `240 s`.

The result stores compact scalar evidence for every root, complete endpoint
states, total-inventory histories, and all 40 shared-time comparisons.

## Decision

A complete pass authorizes only one separately frozen longer open-loop
trajectory contract. Failure stops the physical-policy trajectory path.
Controllers remain unauthorized.
