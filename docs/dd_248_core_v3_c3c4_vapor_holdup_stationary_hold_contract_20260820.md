# DD-248 Vapor-Holdup Stationary Hold Contract

- One `0.25 s` backward-Euler solve from the accepted DD-247 history.
- `least_squares(method="trf")`, 28-color central Jacobian, `h=1e-5`.
- Fixed tight transformed bounds and a maximum of 20 function evaluations.
- Residual below `1e-8`, coordinate movement below `1e-8`, and inventory rates below `1e-5 lbmol/h`.
- Two endpoint Jacobians must retain rank 258 and condition below `1e8`.
- Calls below 100,000 and wall below 180 seconds.
- No disturbance, retry, continuation, controller action, or alternate settings.

Failure stops dynamic work. Success authorizes only one separately frozen small moving-step contract.
