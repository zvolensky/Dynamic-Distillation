# DD-202 Controlled BDF2 Short-Refinement Contract

- Payload SHA-256: `5e161ac0b1be58f20e2e24598de19f791a3178210e422c8487630217c2db21c0`
- Preparation base commit: `d3d4214386f9623da37a3a727258290ea57b1c9b`
- Disturbance/controllers/product references: unchanged from DD-187
- Coarse path: `40 x 0.25 s`
- Refined path: `80 x 0.125 s`
- Each path: one backward-Euler startup, then constant-step BDF2
- Shared-time comparisons: `40`
- Accuracy gate: worst shared inventory max and L1 errors below `0.8 x` DD-190 backward Euler
- Retry, alternate grid, tuning, fallback, or longer trajectory: `False`

Commit this immutable contract before its one execution.
