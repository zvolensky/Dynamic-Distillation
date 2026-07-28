# DD-124 Frozen Controlled-Terminal Zero-Time Contract

- Payload SHA-256: `09b7ce839aac140a52903f05c3e797b35b0a79c96e07cbf1b5c3d131b61c7147`
- System: `50 x 50`, structural rank `50`
- State: exact accepted DD-122 zero-rate root
- Level setpoints: reconstructed once from live density and frozen geometry
- Controller memories: initialized from accepted stationary `D/B` outputs
- Jacobians: two colored central differences and one full cross-check
- Nonlinear solve, timestep, retry, or dynamics: `False`

Execution is permitted once only after this exact contract is committed.
