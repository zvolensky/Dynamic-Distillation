# DD-208 Production-Backend Live Replay Contract

- Payload SHA-256: `7fdabdb1c86298fcbcdab74bac1840558871cbc54f47e9b7917d3720325114fd`
- Path: one `0.125 s` backward-Euler startup plus one `0.125 s` BDF2 root
- Reference: immutable DD-204 accepted parallel reports
- Backend: reusable Core V3 persistent parallel coordinator and BDF2 adapter
- Exact-report limit: `1e-12`
- Trajectory regression limit: `1.25x` DD-204 parallel wall
- Governed wall limit: `60.0 s`
- Retry, alternate step, tuning, fallback, clipping, projection, and longer trajectory: prohibited
