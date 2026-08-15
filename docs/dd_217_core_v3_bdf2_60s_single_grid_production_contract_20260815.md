# DD-217 60-Second Single-Grid Production Contract

- Payload SHA-256: `a952620ebd705d249769289fae9920ecf2006e9129c2d239ba285d8f6c4458ef`
- Path: `240 x 0.25 s`
- Session: one reusable eight-worker DWSIM backend and one final close
- BDF2 initial guess: `linear_extrapolation`
- Active segment / total-session limits: `180.0` / `225.0 s`
- Startup / shutdown / unattributed limits: `10.0` / `30.0` / `1.0 s`
- Saved-science absolute limit: `1e-08`
- Logical provider-call ceiling: `1200000`
- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited

Commit this immutable contract before its one execution.
