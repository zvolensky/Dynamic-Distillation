# DD-195 Controlled BDF2 Structural Contract

## Decision

The property-free structural gate passes. A constant-step BDF2 successor can
reuse the accepted controlled Core V3 equation ownership without adding or
removing a solve variable or physical residual.

## Seven-Volume Result

- Components / physical volumes: `3 / 7`
- Differential states: `23` (`21` component inventories plus `2` PI memories)
- Solve variables / equations: `58 / 58`
- Structural rank / nullity: `58 / 0`
- Fixed history values: `60`
- Component history: `2 x 21`
- Derived internal-energy history: `2 x 7`
- PI-memory history: `2 x 2`
- Property, residual, nonlinear-solve, timestep, and trajectory calls: `0`

The endpoint component and energy derivatives use

`(3*y[n+1] - 4*y[n] + y[n-1]) / (2*dt)`.

Positive component inventories retain the exponential endpoint map; the
component balances receive the exact BDF2 finite-step rate implied by that
endpoint. PI-memory coordinates map exactly to the BDF2 endpoint memory.
Internal energies are not independent state coordinates: both saved history
levels must contain the provider-derived governing storage values associated
with their accepted physical states.

## Startup And Timestep Policy

Exactly one accepted existing backward-Euler controlled step creates the first
history pair. BDF2 is constant-step only in this contract. Any timestep change
invalidates the history and requires a new backward-Euler startup step; history
interpolation or silent coefficient changes are prohibited.

## Genericity

An eight-volume/four-component case has `82` variables, `82` rows, structural
rank `82`, and `84` fixed history values. No interior volume is named or
special-cased.

## Boundary

This pass authorizes only a separately tested BDF2 residual implementation and
a property-free stationary identity audit. It does not authorize a live DWSIM
root, moving step, controller retuning, or trajectory.
