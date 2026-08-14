# DD-211 BDF2 Linear Coordinate Predictor

## Purpose

DD-211 adds one default-off initial-guess policy to the accepted controlled
BDF2 trajectory. It addresses nonlinear work only; it does not change the
dynamic equations, BDF2 history, physical state, property provider, Jacobian,
solver, bounds, or acceptance rules.

## Implementation

The default `accepted_endpoint` policy remains unchanged. Each BDF2 root starts
from the previous accepted solve-coordinate vector.

The optional `linear_extrapolation` policy uses the two most recent accepted
coordinate vectors:

```text
q_guess[n+1] = q[n] + (q[n] - q[n-1])
```

The vector contains all rate, controller-rate, algebraic, and product-log-ratio
coordinates already owned by the solve. Only the initial guess changes. The
nonlinear solver still evaluates and accepts the complete governing residual.

The first BDF2 guess uses the original zero-time coordinates and the accepted
backward-Euler startup coordinates. After every accepted BDF2 root, coordinate
history advances in parallel with the existing physical history. A failed root
does not advance either history.

## Compatibility And Gates

- Default behavior is unchanged.
- The policy is topology- and component-generic.
- Unknown policy names are rejected before a property or solver call.
- No clipping, projection, fallback, or bound modification is added.
- Three new tests cover linear multi-step prediction, unchanged default routing,
  and invalid-policy rejection.
- Twenty-two focused trajectory/backend tests pass with zero live property calls.

## Decision

The property-free implementation passes. `linear_extrapolation` remains
unauthorized for production until one separately frozen eight-worker live
benchmark proves complete roots, physical equivalence, reduced Jacobian work,
and meaningful wall improvement. The accepted default remains
`accepted_endpoint`.
