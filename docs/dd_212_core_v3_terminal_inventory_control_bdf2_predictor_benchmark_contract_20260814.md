# DD-212 BDF2 Linear-Predictor Benchmark Contract

- Payload SHA-256: `277c6a4421d4a4845e5b93a96ce7d85ab22efe446e68874f0f21cbde4404e60a`
- Paths: `40 x 0.25 s` baseline and predictor
- Worker count: `8` with separate fresh pools
- Baseline policy: `accepted_endpoint`
- Candidate policy: `linear_extrapolation`
- Accepted-science absolute limit: `1e-09`
- Required matrix reduction / speedup: `0.1` / `1.1x`
- Governed wall limit: `180.0 s`
- Retry, alternate duration/grid/predictor, tuning, fallback, clipping, projection, or equation change: prohibited

Commit this immutable contract before its one execution.
