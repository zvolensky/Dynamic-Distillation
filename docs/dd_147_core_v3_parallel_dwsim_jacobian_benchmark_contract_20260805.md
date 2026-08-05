# DD-147 Frozen Parallel DWSIM Jacobian Benchmark Contract

- Payload SHA-256: `2f37b414f2f72c479f7824be892953c2be89d82a8daf4e96c61fe837a15bf234`
- State: exact DD-146 first coarse root start
- Work: one complete `50 x 50`, 21-color, central-difference Jacobian
- Pools: fresh spawn-based `1`, `2`, and `4` process workers
- Repetitions: three per worker count in frozen interleaved order
- Process ownership: one independent live DWSIM provider per worker
- Numerical agreement: absolute and relative Frobenius `<=1e-10`
- Meaningful speed gate: four-worker median `<=60%` of serial median
- Projected DD-146-equivalent wall gate: `<75 s` including adjusted pool startup
- Benchmark wall limit: `<300 s`
- Solve, correction, state acceptance, timestep, or trajectory: prohibited

Passing may authorize a separately frozen parallel colored-Jacobian integration contract. Failure retains the serial path.
