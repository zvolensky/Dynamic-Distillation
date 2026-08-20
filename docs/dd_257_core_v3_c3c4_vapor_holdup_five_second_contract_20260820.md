# DD-257 Five-Second Vapor-Holdup Trajectory Contract

- Payload SHA-256: `f8546693a6397bf1b8a13b6df7cf654814cbab9ec35c02333a7d5d0f8611d711`
- Path: 20 serial full-refresh backward-Euler endpoints of `0.25 s` each.
- Disturbance: unchanged `+0.1%` feed and feed enthalpy.
- Replay: the first four endpoints must reproduce DD-254.
- Output: complete final 20-volume temperature, pressure, inventory, composition, and traffic profile.
- Controllers, workers, retries, alternate steps, and extension beyond five seconds: `False`.
