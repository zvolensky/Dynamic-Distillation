# DD-140 Frozen DD-138 Jacobian Repeatability Contract

- Payload SHA-256: `20f282c8839895f08c9070790548d808d857482c02ee87d082b389efdcffb698`
- Points: DD-138 coarse and refined root starts
- Steps: `1e-5` and `5e-6`
- Fresh processes: `3` in grouped-forward, grouped-reverse, and interleaved orders
- Repetitions: `2` complete `50 x 50` matrices per point and step per process
- Jacobian rule: frozen 21-color central difference
- Nonlinear solve, correction, state advance, timestep, and trajectory: prohibited
- Provider-call limit: `<40000`
- Wall-clock limit: `<180 s`

The audit distinguishes Jacobian repeatability from finite-difference step sensitivity. It cannot accept a simulation state.
