# DD-122 Frozen Controlled-Terminal Zero-Rate Contract

- Payload SHA-256: `516cf8e6feb5d4f08a6cb590d2377c2b5bb5db0ee9474066b7badba181d6f5e4`
- System: `48 x 48`, structural rank `48`
- Added unknowns: positive distillate and bottoms level-controller outputs
- Retained targets: reflux-drum and combined-reboiler/sump total inventory
- Starts: DD-120 endpoint and one independent interior/product-rate perturbation
- Solver: one bounded `least_squares(method='trf')` configuration
- Full initial and final residual vectors: required
- Retry, continuation, timestep, controller action, or dynamics: `False`

Execution is permitted once only after this exact contract is committed.
