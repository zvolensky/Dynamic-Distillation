# DD-196 Controlled BDF2 Kinematics And Residual

## Decision

The property-free implementation gate passes. Constant-step BDF2 now has an
explicit history object, endpoint kinematics, and a controlled residual
assembler that reuse the accepted Core V3 physical equations without changing
their ownership.

## Implemented Contract

- Two fixed history levels own every component inventory, provider-derived
  internal energy, and PI memory.
- The BDF2 derivative is
  `(3*y[n+1] - 4*y[n] + y[n-1]) / (2*dt)`.
- Component inventories retain the positive exponential endpoint map. The
  physical component balances receive the effective BDF2 rate implied by that
  endpoint, not the nominal trial coordinate.
- Internal energy remains provider-derived. Its BDF2 storage rate is added once
  to each physical-volume energy balance.
- PI-memory endpoints are obtained by exactly inverting the BDF2 derivative.
- The existing algebraic coordinates, product outputs, controller equations,
  physical residuals, and row scales remain unchanged.
- The implementation is constant-step only. A mismatched timestep or malformed
  history is rejected rather than silently reinterpreted.

## Property-Free Evidence

The focused DD-195/DD-196 suite contains 18 passing tests. It verifies:

- exactly zero derivative for identical endpoint/current/prior histories;
- exact derivatives for linear and quadratic histories;
- PI endpoint inversion with maximum round-trip error
  `1.609823385706477e-15`;
- positive exponential component endpoints and effective BDF2 rates;
- exact zero stationary assembled residual with zero provider calls;
- replacement of nominal component-rate coordinates by the effective BDF2
  coordinates before the physical balances are evaluated;
- eight-volume/four-component genericity;
- rejection of nonpositive inventories, wrong shapes, nonfinite data, and
  timestep changes;
- defensive copying of accepted history.

The stationary derivative and quadratic-polynomial errors are exactly `0.0` in
double precision. The mocked stationary residual, component rates, energy
storage rates, and PI-memory rates are also exactly zero.

The complete Core V3 regression suite passes: `424 passed` in `20.76 s`.

## Meaning

DD-196 removes a numerical-architecture uncertainty. BDF2 can be assembled on
the existing controlled Core V3 model without adding state coordinates,
changing physical equations, or calling the thermodynamic provider during the
kinematic proof.

It does not show that a live DWSIM endpoint reproduces the accepted stationary
root, that the live BDF2 Jacobian retains rank and conditioning, or that BDF2
improves moving-trajectory accuracy. No nonlinear solve, accepted timestep, or
trajectory occurred.

## Next Boundary

One separately frozen live stationary parity audit is authorized. With
identical accepted histories at the DD-185 stationary state, it must compare
the BDF2 and accepted stationary/controlled residuals and numerical Jacobians,
retain zero controller motion, full rank, physicality, provider ownership, and
the existing equilibrium and conservation gates. It may evaluate residuals
and Jacobians only; it may not solve a root, accept a timestep, retune a
controller, or launch a trajectory.
