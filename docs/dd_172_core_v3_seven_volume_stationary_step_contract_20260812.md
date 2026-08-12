# DD-172 Seven-Volume Stationary Implicit-Step Contract

## Purpose

DD-172 is the first authorized timestep for the seven-volume Core V3 model. It
tests whether backward Euler preserves the accepted DD-169 stationary root
without introducing an artificial startup transient.

## Frozen Campaign

- Solve one `1.0 s` backward-Euler root from the accepted state.
- Solve one `0.5 s` root from the same accepted state.
- Solve a second `0.5 s` root from the first half-step endpoint.
- Compare the full-step endpoint with the second half-step endpoint.

Every root uses `least_squares(method="trf")`, topology-generated graph
coloring, central differences at `1e-5`, and a maximum of 20 function
evaluations. Exact-state provider memoization is enabled with exact unrounded
keys and cleared before execution.

## Frozen Gates

- Every root residual below `1e-8`
- Every root Jacobian rank `54/54` and condition below `1e8`
- Component rates below `1e-4 lbmol/h`
- Relative inventory motion below `1e-9`
- Algebraic-coordinate motion below `1e-7`
- Equilibrium residual below `1e-10`
- Component and energy conservation errors below `1e-8`
- Discrete component and energy kinematic identities below `1e-12`
- Positive inventories, compositions, and flows
- Ordered temperature and pressure, negative condenser duty, and valid
  hydraulic heights
- Full/refined inventory, rate-coordinate, and algebraic differences below
  `1e-9`, `1e-7`, and `1e-7`
- Fewer than `30,000` logical provider calls and less than `120 s` wall time

## Scope Boundary

No disturbance, controller, retry, alternate solver, or trajectory is
authorized. Failure stops the dynamic path before moving conditions. A full
pass authorizes only one separately frozen moving-step contract.

## Frozen Artifact

- `logs/dd172_core_v3_seven_volume_stationary_step_contract_20260812.json`
- Payload SHA-256:
  `1b7851ea5ae6cf10c82135a5b8f6b9bb52a02392cbaec1f12da72b8a62e1dd8e`
