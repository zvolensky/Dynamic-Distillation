# DD-168 Frozen Seven-Volume Numerical-Audit Contract

## Question

Does the structurally accepted DD-167 seven-volume Core V3 ledger remain
numerically complete and physically evaluable with live DWSIM Peng-Robinson
properties at one independently source-mapped state?

## Frozen State

The reference is mapped directly from seven distinct roles in the existing
eight-location C3/C4 source workbook:

- reflux-drum boundary;
- two rectifying section volumes;
- feed volume;
- two stripping section volumes;
- combined reboiler/sump boundary.

The source mapping supplies liquid holdup, liquid and vapor composition,
temperature, pressure, and flow references. A local direct-fugacity bubble
solve constructs only the saturated-liquid condenser boundary, and the
condenser duty is reconstructed directly from its energy balance. No complete
column residual, material/energy balance solve, imported Core V3 root, or
dynamic state is used to construct the point.

## Frozen Numerical Audit

- Dimension: `56 x 56`.
- Provider: DWSIM Peng-Robinson for every governing property.
- Jacobian: uncolored central difference.
- Relative coordinate steps: `1e-5` and `5e-6`.
- Unexpected-coupling threshold: `1e-7`.
- Required full rank: `56` at both steps.
- Required condenser local rank: `3` at both steps.
- Condition limit: `<1e8`.
- Singular-spectrum relative change: `<0.25`.
- Component telescoping: `<1e-12` relative.
- Energy telescoping: `<1e-10` relative.
- Bubble fugacity residual: `<1e-10`.
- Provider calls: `<20,000`.
- Governed wall time: `<120 s`.

The audit also requires positive physical amounts and flows, negative condenser
duty, positive liquid density and over-weir head, liquid height below spacing,
TP-flash internal consistency, parameter-aligned independent-PR bubble
agreement, exact condenser-duty ownership, and no fallback, clipping, or
projection.

## Hard Boundary

This contract authorizes exactly one execution after the contract and
implementation are committed. It authorizes no nonlinear solve, root
acceptance, timestep, initializer, mass-matrix work, controller, or dynamic
integration.

Passing authorizes only one separately frozen seven-volume stationary-root
campaign. Failure stops the seven-volume scale-up before a solve.

## Frozen Artifact

- `logs/dd168_core_v3_seven_volume_numerical_contract_20260806.json`
- Contract payload SHA-256:
  `705dc02b92a4fcc8f272db0f0b6d1637b251e5d9b7a59aab57e7c6a667de5870`
