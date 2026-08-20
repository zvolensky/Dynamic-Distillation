# DD-267 Short Controlled Trajectory Contract

- Payload SHA-256: `6e00fc0f578a9388f3df9ae9812ee9f6e407fd0f16899a6bd2168dffc2a1162e`
- Source endpoint: `0.25 s` from DD-265/DD-266.
- Nominal continuation: `3` x `0.25 s` to `1.0 s`.
- Final refinement: `2` x `0.125 s` from `0.75 s`.
- Both PI memories and absolute product-output coordinates continue across every endpoint.
- Each new root receives one fresh 16-color Jacobian held only within that root.
- Residual, physicality, conservation, controller direction, continuity, refinement, provider, call, and wall gates are mandatory.
- Retry, alternate grid, tuning change, fallback, parallel worker, or extension: `False`.
