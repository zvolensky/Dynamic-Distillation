# DD-229 Aligned-PR Density Parity Audit

## Result

The explicit property routing passes:

- DWSIM continues to own imposed-phase fugacity and phase enthalpy;
- the parameter-aligned PR calculation owns liquid density;
- all four `160 x 160` Jacobians retain rank 160;
- conditions fall to `3.36e6` at the source endpoint and `4.02e5` at the independent endpoint;
- singular-spectrum changes between `1e-5` and `5e-6` are below `4e-9`;
- full-matrix relative changes are about `1.5e-10`;
- density remains within `0.484-0.650 lbmol/ft3` across the column;
- physicality, conservation, and provider-routing gates pass;
- `12,474` logical provider calls complete in `5.643 s`;
- no solve, state change, timestep, or dynamic integration occurs.

For comparison, the original DWSIM-density endpoint conditions were `1.20e9-2.09e10`, and their finite-difference matrix changes were nearly 100%.

## Residual movement

The scaled residuals increase from `4.31e-4` to `0.1204` and from `0.0123` to `0.1436`. This is expected: the saved DD-223 endpoints were adjusted against DWSIM's discontinuous density branches. Once density is made smooth and phase-explicit, their old hydraulic flows are no longer consistent.

The endpoints are therefore diagnostic starts, not roots or dynamic initial conditions.

## Decision

The aligned-PR density route is numerically viable for governing hydraulics. Before one new stationary-root campaign, derive one fixed coordinate-scale vector from the four saved DD-229 matrices and verify that it improves or at least preserves conditioning at both endpoints. No live calls are needed for that design.

Root solving and dynamics remain stopped until that fixed scaling is frozen.
