# DD-199 Controlled BDF2 Short-Refinement Contract

- Payload SHA-256: `ed3ce37a3a1fbeb73ff3dffb56eec23463ca864f2c946dd57c6b3fb969b67f7f`
- Preparation base commit: `bd9d4b23485426b6e1470eccdff3ca7b2fd7d560`
- Disturbance/controllers/product references: unchanged from DD-187
- Coarse path: `8 x 0.25 s`
- Refined path: `16 x 0.125 s`
- Each path: one backward-Euler startup, then constant-step BDF2
- Shared-time comparisons: `8`
- Accuracy gate: worst shared inventory max and L1 errors below `0.8 x` DD-188
- Retry, alternate grid, tuning, fallback, or longer trajectory: `False`

Commit this immutable contract before its one execution.
