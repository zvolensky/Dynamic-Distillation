# DD-099 Core V3 Performance-Correction Contract

## Purpose

DD-098 proved the short implicit trajectory but required `325,332` DWSIM
calls for eight endpoints. DD-099 is a bounded numerical-equivalence and
performance audit before any longer trajectory.

## Frozen correction

1. Internal-energy storage uses the endpoint liquid enthalpy and density
   already returned by the governing residual. It does not reconstruct five
   independently saturated states inside every residual evaluation.
2. All five volume densities are evaluated directly in the governing property
   packet. This adds two terminal-density calls and removes the nested bubble,
   duplicate enthalpy, and duplicate density calculations.
3. The backward-Euler Jacobian may use deterministic structural coloring. Its
   sparsity includes both direct solve dependencies and the endpoint-inventory
   chain from rates to state-dependent equations.
4. The frozen pattern has 38 columns and 17 conflict-free color groups. Central
   differences therefore require 34 residual evaluations instead of 76.

No approximate property cache, tolerance reuse, clipping, fallback,
continuation, controller, or altered physical equation is permitted.

## Single execution

Execute four independent `1.0 s` backward-Euler solves from the DD-094 root:

- stationary root, uncolored Jacobian;
- stationary root, colored Jacobian;
- `+0.1%` feed-throughput step, uncolored Jacobian;
- `+0.1%` feed-throughput step, colored Jacobian.

Both Jacobian methods must pass the existing residual, rank, condition,
equilibrium, conservation, physicality, and provider gates. Colored and
uncolored endpoints must agree within the frozen limits in the JSON contract.
No implicit residual evaluation may call the nested bubble reconstruction.

## Performance gate

The colored method must:

- use fewer provider calls than the uncolored method in each case;
- remain below `10,000` provider calls per solve;
- reduce mean calls by more than `5x` relative to DD-098's `40,666.5` calls
  per endpoint.

Failure stops the longer-trajectory path without tuning. Passing authorizes
only one separately frozen modest open-loop trajectory contract.
