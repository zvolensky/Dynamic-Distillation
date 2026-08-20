# DD-255 Modified-Newton Vapor-Holdup Trajectory Contract

- Payload SHA-256: `51408ed56e5da4f323e33b98d317202880e5980b0bd0095ff3dd412adeed95fd`
- Path: four serial `0.25 s` endpoints under the unchanged DD-254 disturbance.
- Jacobian: one fresh 28-color matrix at the start of each root, then fixed within that root.
- Reference: all four accepted DD-254 serial endpoints.
- Endpoint, residual, conservation, physical, rank, and provider gates remain mandatory.
- Calls must fall below 30% and wall below 65% of DD-254 serial.
- Retry, alternate grid, parallel worker, controller, or longer trajectory: `False`.
