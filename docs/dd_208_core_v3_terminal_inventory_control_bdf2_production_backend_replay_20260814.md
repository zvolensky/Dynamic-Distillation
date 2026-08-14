# DD-208 Production-Backend Live Replay Result

- Classification: `controlled_bdf2_production_backend_replay_passed`
- Decision: `retire_campaign_local_parallel_bdf2_closures`
- Completed roots / Jacobians: `2` / `7`
- Maximum report difference: `0.000000e+00`
- Reference / production trajectory wall: `7.369045` / `8.551296 s`
- Wall ratio: `1.160x`
- Adjusted startup / governed wall: `2.005` / `17.103 s`
- Logical provider calls: `8602`
- Retry, tuning, alternate step, or fallback: `False`

## Assessment

All frozen gates pass. Both accepted root reports are exactly equal to the
immutable DD-204 parallel reports after their common JSON representation, with
maximum numerical difference `0.0`. Worst residual remains `1.868842e-12`,
rank remains `58`, and worst condition remains `3.172741e7`.

The reusable coordinator produces seven Jacobians. Every matrix uses all four
workers, and the backward-Euler and BDF2 roots each record exactly four total
worker-basis rebuilds. Main-process and worker provider ownership pass without
fallback.

Production-backend trajectory wall is `8.551296 s` versus the historical
DD-204 parallel reference of `7.369045 s`, a `1.160x` ratio within the frozen
`1.25x` limit. The small replay is startup-sensitive; DD-205 remains the
accepted long-path economics evidence. Campaign-local parallel closures are
retired for future work but retained as immutable historical artifacts.
