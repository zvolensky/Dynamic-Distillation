# DD-269 Five-Second Controlled Trajectory Contract

- Payload SHA-256: `a818e2c85622d7ad80da1726805eea55234e486543f46324d0c8f406aa36ddd2`
- Saved replay: `4` endpoints through `1.0 s` without solving.
- New continuation: `16` x `0.25 s` to `5.0 s`.
- Final refinement: `2` x `0.125 s` from `4.75 s`.
- Each new root receives one fresh 16-color Jacobian held only within that root.
- Refinement inventory differences must equal differences in integrated controlled boundaries.
- Endpoint journals, final profile, conservation, continuity, provider, call, and wall gates are mandatory.
- Retry, alternate grid, tuning change, fallback, parallel worker, or extension: `False`.
