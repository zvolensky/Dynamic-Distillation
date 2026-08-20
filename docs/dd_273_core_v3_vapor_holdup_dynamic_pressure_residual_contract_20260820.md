# DD-273 Dynamic-Pressure Residual Contract

- Payload SHA-256: `7198e9f5a6252136252891b964d15960531783d46c4324715af5db04b199f8d3`
- Replay all 120 accepted DD-271 endpoints without solving.
- Fix condenser duty at the accepted endpoint value.
- Evaluate one next-step predictor and Jacobians at `1e-5` and `5e-6`.
- Require rank 262, condition below `1e8`, stable matrices, exact duty-row derivative, and provider ownership.
- Nonlinear solve, accepted timestep, retry, tuning, or fallback: `False`.
