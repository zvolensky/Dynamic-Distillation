# DD-129 Core V3 Controlled-Terminal Moving-Step Abort

- Classification: `dd129_aborted_during_result_serialization`
- Decision: `stop_before_any_retry_or_trajectory`
- Contract commit: `d5c9fcb`
- Scientific gate result: `not available`
- Retry: `False`
- Dynamic trajectory: `False`

The frozen campaign completed its three requested solve paths and reached final
result assembly. JSON serialization then rejected
`gates.controller_direction` because the expression returned a NumPy boolean
rather than a native Python boolean. No result artifact or retained scientific
metrics were produced.

This is a reporting-interface abort, not evidence that the controlled moving
step passed or failed. The frozen no-retry rule remains in force. A successor
requires explicit authorization and must change only JSON-safe gate coercion,
add a serialization regression test, and retain the DD-129 disturbance, grids,
solver, physical gates, and limits unchanged.
