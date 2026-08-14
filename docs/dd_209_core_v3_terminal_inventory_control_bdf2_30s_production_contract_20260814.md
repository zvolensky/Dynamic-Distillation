# DD-209 30-Second Production BDF2 Contract

- Payload SHA-256: `629c48e68fae4dd77aa9d60af742ed7fd245eff1a925b71daca1f585f1371eab`
- Coarse path: `120 x 0.25 s`
- Refined path: `240 x 0.125 s`
- Backend: accepted reusable four-worker persistent parallel backend
- Science: unchanged DD-202 disturbance, controllers, equations, and DWSIM PR provider
- Refinement: frozen absolute physical/controller/response limits; DD-202 ratios are diagnostic only
- Logical provider-call ceiling: `2000000`
- Governed wall deadline: `300.0 s`
- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited

Commit this immutable contract before its one execution.
