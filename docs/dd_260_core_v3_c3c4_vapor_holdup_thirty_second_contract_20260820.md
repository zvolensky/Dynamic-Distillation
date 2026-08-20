# DD-260 Thirty-Second Vapor-Holdup Contract

- Payload SHA-256: `7334686b0b70ebad928e28d4946a5e092c4c4347f2cf1898b9dac4cfd92d966e`
- Nominal path: `120` x `0.25 s` endpoints.
- Final refinement: `2` x `0.125 s` from `29.75 s`.
- Physics, disturbance, operating inputs, and modified-Newton method are inherited unchanged from DD-259.
- Every endpoint must remain physical, conservative, full rank, smooth, and recoverable.
- No controller, retry, fallback, tolerance change, or extension is authorized.
