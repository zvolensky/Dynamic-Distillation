# DD-256 Broyden Vapor-Holdup Trajectory Result

- Classification: `broyden_vapor_holdup_trajectory_aborted_before_endpoint`
- Decision: `retire_low_cost_jacobian_reuse`
- Accepted endpoints: `0`
- State advance accepted: `False`
- Failure: SciPy requested a later Jacobian at unchanged coordinates.
- Consequence: no nonzero coordinate/residual secant existed for the mandatory update.
- Frozen hard stop: skipping a requested update was prohibited.
- Retry, patch-and-rerun, alternate update, damping, reset, worker, controller, or extension: `False`

The abort is a solver-callback compatibility failure, not a thermodynamic or
conservation failure. DD-256 is not rerun. The DD-254 full-refresh serial path
remains the accepted scientific implementation. Low-cost fixed or secant
Jacobian reuse is retired under the current solver architecture.
