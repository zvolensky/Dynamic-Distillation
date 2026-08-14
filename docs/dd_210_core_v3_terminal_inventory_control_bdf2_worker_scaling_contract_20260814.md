# DD-210 Four-Versus-Eight Worker Scaling Contract

- Payload SHA-256: `71080e550c95f8e964134f92375287b3b8ef2bddaa9726ba40595a2df658c4e0`
- Each path: one `0.125 s` backward-Euler startup plus one `0.125 s` BDF2 root
- Science and source backend: unchanged from accepted DD-208/DD-209
- Compared worker counts: `4` and `8`
- Matrix/report absolute limit: `1e-12`
- Required warm-trajectory speedup: `1.3x`
- Governed wall limit: `120.0 s`
- Retry, alternate worker count, tuning, fallback, clipping, projection, and longer trajectory: prohibited

Commit this immutable contract before its one execution.
