# DD-132 Frozen Modified-Newton Live Efficiency Contract

- Payload SHA-256: `a9db7158e336973caccedc6f2710eb19ddbbb67dced6572407cc3f5085fac25b`
- Physical state, disturbance, and grids: exact DD-130
- Solver: one frozen 21-color Jacobian and one LU factorization per root
- Corrections/line search: at most `12 / 4` per root
- Saved DD-130 endpoint reproduction limit: `1e-7` normalized
- Provider-call limit: `<8000`
- Rebuild, fallback, retry, or trajectory: `False`

Execution is permitted once only after this exact contract is committed.
