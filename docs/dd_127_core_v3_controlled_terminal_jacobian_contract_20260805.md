# DD-127 Frozen Controlled-Terminal Jacobian Contract

- Payload SHA-256: `872ee0c1d7e7bf87fd7250d9c3564ad50ba7ccc475aab8955a08b58ddfff4ad7`
- System: `50 x 50`, structural rank `50`
- State: exact accepted DD-122 zero-rate root
- Level setpoints: `{'drum_fraction': 0.4692884263369592, 'sump_fraction': 0.5249566359186797}` frozen from DD-126
- Controller memories: initialized from accepted stationary `D/B` outputs
- Jacobians: two colored central differences and one full cross-check
- Nonlinear solve, timestep, retry, or dynamics: `False`

Execution is permitted once only after this exact contract is committed.
