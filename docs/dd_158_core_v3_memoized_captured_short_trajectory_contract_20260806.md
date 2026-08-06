# DD-158 Frozen Memoized Captured Short-Trajectory Contract

- Payload SHA-256: `c30cbbc4c64051a2a16085819785e487ad898e629c84103174427b58bde24210`
- Scientific case: exact DD-149/DD-144 `10 s`, `10 x 1.0 s` and `20 x 0.5 s`
- Only change: production exact memoization with one unique epoch per Jacobian
- Exact work: 30 roots, 1,260 tasks, 35,280 logical worker-provider calls
- Equivalence: complete captures and accepted states `<=1e-10` versus DD-149
- Memo accounting: 1,176 calls/root and hit fraction `>=0.60` for every root
- Performance: trajectory wall `<=0.75x` DD-149; total wall `<30 s`

Passing may authorize only a separately frozen longer memoized trajectory. Multi-minute operation remains unauthorized.
