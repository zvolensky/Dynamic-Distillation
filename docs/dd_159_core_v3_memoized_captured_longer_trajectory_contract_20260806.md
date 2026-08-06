# DD-159 Frozen Memoized Captured 60-Second Trajectory Contract

- Payload SHA-256: `315be0cb9f9b4ec4b6e22772738c5b80eb817d4979698229272b3834136c60a1`
- Scientific case: exact DD-150/DD-146 `60 s`, `60 x 1.0 s` and `120 x 0.5 s`
- Only change: production exact memoization with one unique epoch per Jacobian
- Exact work: 180 roots, 7,560 tasks, 211,680 logical worker-provider calls
- Equivalence: complete captures and accepted states `<=1e-10` versus DD-150
- Memo accounting: 1,176 calls/root and hit fraction `>=0.60` for every root
- Performance: trajectory wall `<=0.80x` DD-150; total wall `<60 s`

Passing may authorize only a separately frozen five-minute memoized trajectory.
