# DD-242 Stationary Vapor-Holdup Initializer Contract

- Classification: `vapor_holdup_stationary_contract_passed`
- Decision: `authorize_stationary_numerical_residual_implementation`
- Property calls, residuals, solves, and timesteps: `False`

## Result

- Five-volume development system: `65 x 65`, rank `65`
- Twenty-volume C3/C4 system: `260 x 260`, rank `260`
- Structural nullity: `0` in both systems
- Zero or unregistered rows/variables: `0`

## Plain-Language Design

The initializer solves the actual resident liquid and vapor inventories at steady state. It fixes the reflux-drum and sump liquid inventories at their geometry-based level targets, while distillate and bottoms rates become solved variables. This closes the two terminal level degrees of freedom without adding controllers or pretending that a dynamic step is a steady-state solution.

## Boundary

This is a structural result only. It authorizes implementation of one live stationary residual; it does not authorize a root solve or dynamic integration.
