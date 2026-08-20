# DD-271 Bound-Corrected Controlled Trajectory Contract

- Payload SHA-256: `ab4c5252e36cf0f998b83a20c764112f0635071b9376e0b6a31efd3f932f7769`
- Saved replay: `26` endpoints through `6.5 s` without solving.
- New continuation: `94` x `0.25 s` to `30.0 s`.
- Final refinement: `2` x `0.125 s` from `29.75 s`.
- Product-output log bounds come from the existing physical rate-ratio contract: `log(0.25)` to `log(2.0)`.
- Each new root receives one fresh 16-color Jacobian held only within that root.
- Refinement inventory differences must equal differences in integrated controlled boundaries.
- Endpoint journals, final profile, conservation, continuity, provider, call, and wall gates are mandatory.
- Retry, alternate grid, tuning change, fallback, parallel worker, or extension: `False`.
