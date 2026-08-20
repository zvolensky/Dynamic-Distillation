# DD-256 Broyden Vapor-Holdup Trajectory Contract

- Payload SHA-256: `94f5b8b9fcb83e1675d235cea872954aa8b6be816362e02486a0d6f60f005baf`
- Path: four serial `0.25 s` endpoints under the unchanged disturbance.
- Each root begins with one fresh 28-color finite-difference Jacobian.
- Later Jacobian callbacks use the fixed good-Broyden rank-one secant formula.
- Every new endpoint discards the old matrix and starts fresh.
- All DD-255 scientific and DD-254 endpoint-reference gates remain fixed.
- Retry, alternate update, damping, reset, worker, controller, or extension: `False`.
