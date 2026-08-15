# DD-215 Reusable Production-Session Proof Contract

- Payload SHA-256: `732f1b4025d847d76416096c6b3d4bcaeb3c5766c8cc662782afc5fef2935619`
- Coarse path: `8 x 0.25 s`
- Refined path: `16 x 0.125 s`
- Lifecycle: one eight-worker session, two uniquely named trajectories, one final close
- Predictor: `linear_extrapolation`
- Science: unchanged DD-213 equations, controls, solver, grids, and DWSIM PR provider
- Logical-call / total-wall ceilings: `180000` / `120.0 s`
- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited

Commit this immutable contract before its one execution.
