# DD-137 Captured Modified-Newton Result

- Classification: `captured_modified_newton_ready`
- Decision: `authorize_separately_frozen_live_in_process_failure_capture_contract`
- Full-rank fixture: rank `50/50`, residual `0.000e+00`
- Line-failure trials captured: `4`
- Alias residual/coordinate mismatch: `1.250000e-01` / `1.250000e-01`
- Bounded trials rejected before evaluation: `2`
- All capture arrays read-only: `True`

No live property, column residual/Jacobian, column solve, state advance, timestep, or trajectory was attempted.

## Interpretation

The versioned tracer preserves complete, immutable globalization evidence without changing the historical DD-131/DD-134 solver. The 50-dimensional full-rank fixture converges with exact residual and coordinate identity. The failure fixture retains all four rejected Armijo trials, the bounded fixture records two unevaluated out-of-bound candidates, and the singular fixture retains rank-zero evidence.

The deliberately shared mutable evaluation buffer leaves the solver's immutable initial/final residuals at `1.0` while the retained evaluation is later mutated to `1.125`; both identity metrics report the exact `0.125` mismatch. This proves the tracer can distinguish solver state from mutable evaluation state rather than silently serializing whichever value remains at report time.

One separately frozen live in-process failure-capture diagnostic contract is authorized. It must remain diagnostic and may not advance a state or trajectory.
