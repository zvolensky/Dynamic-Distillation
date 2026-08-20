# DD-250 Vapor-Holdup Short Trajectory Contract

- Payload SHA-256: `1fa887209e13fe781cb01eb9ec5a848db74abd3ef5895a2aa9fdbeba41fff1e6`
- Disturbance: `+0.1%` feed component rates and feed enthalpy.
- Duration: `1.0 s`.
- Nominal path: `4` endpoints at `0.25 s`.
- Refined path: `8` endpoints at `0.125 s`.
- Products, reflux, reboiler duty, and top-pressure anchor remain fixed.
- Every endpoint must remain full rank, conservative, physical, and provider-governed.
- Retry, alternate grid, controller action, or longer trajectory: `False`.

Failure stops trajectory extension. Passing authorizes only a separately frozen dynamic-scope decision.
