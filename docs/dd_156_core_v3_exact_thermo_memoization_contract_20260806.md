# DD-156 Frozen Exact-State Thermo Memoization Contract

- Payload SHA-256: `d1092cfb8d6cac10993fafed274d7a903d5ba55a5b858d6d5c62dab1ef56eed2`
- State: saved DD-151 coarse root `180`
- Stages: uncached pass-through, cold exact memo, warm exact memo
- Scope: fugacity, phase enthalpy, liquid density, vapor Z, and molecular weight
- Exact keys: phase, unrounded float temperature/pressure, and unrounded composition tuple
- Exact work: one four-worker pool, 3 matrices, 126 tasks, 3,528 logical governing calls
- Matrix reproduction: `<=1e-10` absolute
- Performance: warm speedup `>=1.50x`, warm hit fraction `>=0.50`
- Wall limit: `<60 s`

Passing may authorize only a separately implemented bounded exact-state memoization layer plus saved-state equivalence benchmark. No trajectory is authorized.
