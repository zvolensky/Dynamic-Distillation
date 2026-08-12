# DD-177 Seven-Volume Physical-Policy Short-Trajectory Contract

## Purpose

DD-177 is the first trajectory contract under the prospective DD-176 physical
accuracy policy. It does not reclassify or rerun DD-175. It tests repeated
moving roots over a common two-second horizon before any controller or longer
operation is considered.

## Frozen Experiment

- initial state: accepted DD-169 seven-volume stationary root;
- disturbance: unchanged `+0.1%` increase in every feed component flow and
  total feed enthalpy, preserving feed composition and specific enthalpy;
- coarse path: `8 x 0.25 s`;
- refined path: `16 x 0.125 s`;
- shared comparisons: all eight coarse endpoints against refined endpoints at
  the same physical times;
- solver, colored Jacobian, scaling, DWSIM PR ownership, and exact unrounded
  memoization: unchanged;
- controllers, clipping, projection, fallback, retry, alternate grid, and
  continuation: prohibited.

## Gates

Every root must close below `1e-8`, retain rank `54`, remain below condition
`1e8`, and pass equilibrium, physicality, conservation, and exact discrete
kinematics. Both paths must complete, accumulate inventory positively and
monotonically, and match integrated external component flow within
`1e-6 lbmol`.

At every shared time, the DD-176 inventory policy requires maximum absolute
component difference `<1e-4 lbmol`, `1 lbmol`-floor-relative difference
`<1e-5`, volume-holdup-relative difference `<1e-6`, L1 difference
`<2e-4 lbmol`, and absolute signed total difference `<1e-9 lbmol`. Rate and
algebraic-coordinate differences must remain below `1e-5`.

The unfloored component-relative maximum is recorded at every shared time but
is not a gate. Logical provider calls must remain below `150,000`, and wall
time below `180 s`.

## Decision

A complete pass authorizes only one separately frozen modest open-loop
extension under the same physical policy. Failure stops this trajectory path.
Controllers remain unauthorized.
