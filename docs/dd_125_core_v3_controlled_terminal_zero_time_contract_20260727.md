# DD-125 Frozen Controlled-Terminal Zero-Time Contract

- Payload SHA-256: `b0ac5be9c77320ddf0314a34d471f28b86d0eb7e4216cf2acbf01211964a4c9a`
- System: `50 x 50`, structural rank `50`
- State: exact accepted DD-122 zero-rate root
- Level setpoints: reconstructed once from live density and frozen geometry
- Controller memories: initialized from accepted stationary `D/B` outputs
- Jacobians: two colored central differences and one full cross-check
- Nonlinear solve, timestep, retry, or dynamics: `False`

Execution is permitted once only after this exact contract is committed.
