# DD-218 Five-Minute Dynamic Production Contract

- Payload SHA-256: `0862f07117536e0bd303f8d1450d4cbc042892abff1a6fa06268d1bdda7ded0b`
- Path: `1200 x 0.25 s = 300.0 s`
- Model: accepted seven-volume Core V3 controlled DAE with DWSIM PR
- Session: one reusable eight-worker backend and one final close
- Initial guess: `linear_extrapolation` after one backward-Euler startup
- Active / total-session limits: `900.0` / `960.0 s`
- Logical provider-call ceiling: `5500000`
- DD-217 60-second prefix limit: `1e-08`
- Evidence: canonical full hashes plus first/every-5.0-second/final samples
- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited

Commit this immutable contract before its one execution.
