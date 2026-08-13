# DD-181 Seven-Volume Parallel Jacobian Benchmark Contract

- Payload SHA-256: `7cfd721b20eeee6dd3dc72636fea7d9793a2cd10dfec238f935f829d10b60dd2`
- State: DD-180 first coarse-step initial point
- Matrix: `54 x 54`, `17` colors, `34` residual tasks
- Workers: `1`, `2`, and `4`; three fresh spawned pools each
- Numerical gate: matrix, rank, singular spectrum, and condition equivalence
- Performance gate: four-worker median `<=75%` of one-worker median
- Solve, state advance, controller, and trajectory: prohibited

DD-180 production-equivalent path: `136.517 s` wall for `30 s` simulated.
