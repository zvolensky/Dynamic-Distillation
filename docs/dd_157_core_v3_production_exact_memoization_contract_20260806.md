# DD-157 Frozen Production Exact-Memoization Proof Contract

- Payload SHA-256: `2d6ca789f7104609bab2f775a6bb34d09b8d2578739b637dcf724cfd0406fb30`
- States: DD-151 coarse root `180` and refined root `360`
- Modes: uncached, then production exact memo with a unique per-Jacobian epoch
- Exact work: one four-worker pool, 4 matrices, 168 tasks, 4,704 logical calls
- Matrix reproduction: `<=1e-10` absolute
- Each state: speedup `>=1.50x`, memo hit fraction `>=0.60`
- Wall limit: `<60 s`

Passing authorizes only a separately frozen short-trajectory integration proof. It does not authorize multi-minute operation.
