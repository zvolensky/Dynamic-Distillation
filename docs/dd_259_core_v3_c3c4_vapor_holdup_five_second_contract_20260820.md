# DD-259 Recoverable Five-Second Vapor-Holdup Contract

- Payload SHA-256: `2c718f13eb66e2c03d940631a86a30356e9300865ae1b1996c5c1f399d872de1`
- Authorization: explicit user override; DD-255/DD-257/DD-258 remain unchanged.
- Path: 20 serial `0.25 s` endpoints with one fresh Jacobian per root.
- Replay: non-duty coordinates `<=1.0e-09`; condenser duty relative `<=1.0e-08`.
- Recovery: one atomic JSON checkpoint after every accepted endpoint.
- Final artifacts: validated atomic JSON, NPZ, and full 20-volume profile.
- Retry, alternate setting, worker, controller, fallback, or extension: `False`.
