# DD-171 Seven-Volume Dynamic DAE Numerical Contract

## Purpose

DD-171 is the single numerical successor authorized by DD-170. It tests
whether the accepted DD-169 seven-volume stationary root is a numerically
consistent zero-rate point of the conserved dynamic DAE and whether the live
leading system is usable before any timestep is attempted.

## Frozen Work

- Reconstruct the 21 component inventories from the accepted DD-169 root.
- Reconstruct the 33 dynamic algebraic coordinates without a property call.
- Evaluate the live DWSIM Peng-Robinson storage gradient at relative steps
  `1e-5` and `5e-6`.
- Evaluate the zero-rate 54-row dynamic residual.
- Build complete central-difference `54 x 54` leading Jacobians at `1e-5` and
  `5e-6`.
- Audit rank, condition, singular-spectrum stability, registered coupling,
  conservation, provider provenance, calls, and wall time.

Exact-state, unrounded provider memoization is enabled and cleared before the
campaign. It may reduce repeated delegated work but may not change equations,
coordinates, scales, or acceptance.

## Frozen Gates

- Zero-rate scaled residual below `1e-8`
- Exactly zero component and energy-storage rates
- Finite storage gradient with relative step change below `1e-3`
- Bubble reconstruction residual below `1e-10`
- Both leading Jacobians rank `54/54`
- Condition below `1e8`
- Singular-spectrum change below `0.25`
- No zero rows, zero columns, or off-contract couplings above `1e-7`
- Component and energy conservation below `1e-12` and `1e-10`
- Clean provider provenance
- Fewer than `30,000` logical provider calls and less than `120 s` wall time

## Scope Boundary

DD-171 may not solve for a state, select a timestep, execute a controller, or
integrate dynamics. Failure stops the seven-volume dynamic path before a
timestep. A complete pass authorizes only one separately frozen stationary
root-hold implicit-step contract.

## Frozen Artifact

- `logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_contract_20260812.json`
- Payload SHA-256:
  `f1dbdc61d411da0c198f72a3792ee2c9f88410ad1e8396752ad8981bf417cf1a`
