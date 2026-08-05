# DD-129 Frozen Core V3 Controlled-Terminal Moving-Step Contract

- Payload SHA-256: `af91f1b674e404d774b8706fbcad161f67a12c068c7e68917fb00f44c7c9d325`
- Disturbance: both physical level setpoints `+0.1%` relative
- Grid: `1 x 1.0 s` versus `2 x 0.5 s`
- Feed, duties, thermo, tuning, and equations: unchanged
- Endpoint Jacobian: reuse solver matrix plus one independent spectrum matrix
- Trajectory: `False`

Execution is permitted once only after this exact contract is committed. Passing authorizes only a separately frozen short trajectory contract.
