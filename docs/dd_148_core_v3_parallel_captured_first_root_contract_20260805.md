# DD-148 Frozen Parallel Captured First-Root Contract

- Payload SHA-256: `d1034f6ca862c35cc1fef0e21ee093bfc78f6baa8326c31b62b1ce9123fb89ac`
- Root: exact DD-146 first coarse implicit root
- Solves: one serial and one four-worker parallel captured modified-Newton solve
- Residual/line search: same main-process DWSIM provider and objective
- Parallel work: frozen 21-color central-difference Jacobian only
- Matrix equality: exact
- Captured root/correction/trial equality: `<=1e-12`
- DD-146 root reproduction: `<=1e-10`
- Endpoint acceptance, timestep, or trajectory: prohibited
- Wall-clock limit: `<180 s`

Passing may authorize one separately frozen parallel captured short-trajectory contract. Failure retains the serial trajectory path.
