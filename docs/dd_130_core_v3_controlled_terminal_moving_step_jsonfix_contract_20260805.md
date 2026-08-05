# DD-130 Frozen Controlled-Terminal Moving-Step JSON Fix

- Payload SHA-256: `d69cfaf7ecfdec038dd877d4f0370b938a4b53cb0dcd39622c6390bbba77c0e7`
- Scientific contract relative to DD-129: `identical`
- Runtime change: recursively coerce only `numpy.bool_` values to native `bool` before JSON serialization
- Disturbance, grids, solver, gates, and limits: `unchanged`
- Retry or trajectory before commit: `False`

Execution is permitted once only after this exact contract is committed.
