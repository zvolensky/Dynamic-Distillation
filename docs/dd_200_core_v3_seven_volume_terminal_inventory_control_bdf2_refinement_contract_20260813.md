# DD-200 Controlled BDF2 Short-Refinement Contract

- Payload SHA-256: `c364fa5f9d1e2769a761b4e36fc0d383c5cf52a6a62f0d17226b4714fc6d863c`
- Preparation base commit: `5001f14ee7ee7bfe04db40d79c8fa361dbc82c9b`
- Disturbance/controllers/product references: unchanged from DD-187
- Coarse path: `8 x 0.25 s`
- Refined path: `16 x 0.125 s`
- Each path: one backward-Euler startup, then constant-step BDF2
- Shared-time comparisons: `8`
- Accuracy gate: worst shared inventory max and L1 errors below `0.8 x` DD-188
- Retry, alternate grid, tuning, fallback, or longer trajectory: `False`

Commit this immutable contract before its one execution.
