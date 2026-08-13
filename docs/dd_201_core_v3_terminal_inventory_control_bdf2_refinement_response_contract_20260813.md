# DD-201 BDF2 Response Adjudication Contract

- Payload SHA-256: `7fbb16ae0a0f00f25efa97c8db474acd8441c29db9c47261f0bf25a419b40db1`
- Preparation base commit: `40188203189b206e3ca90b106366cb3ce9b53076`
- DD-200 formal failure retained: `True`
- Inputs: immutable saved inventories plus feed/distillate/bottoms rates
- Expected response: BE startup followed by constant-step BDF2 recurrence
- Unexplained difference limit: `<1e-10 lbmol`
- Response-relative difference limit: `<1e-5`
- Model/provider/solver/endpoint-regeneration calls: `0`

Commit before the one zero-call execution.
