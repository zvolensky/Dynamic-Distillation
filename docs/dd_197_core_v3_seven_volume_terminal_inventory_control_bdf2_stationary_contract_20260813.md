# DD-197 Controlled BDF2 Stationary Parity Contract

- Payload SHA-256: `b7fa80892f4ef0ec1b9e9e076a082b95d2686790484cc14a9f182b943b4ed187`
- Preparation base commit: `ee84ba66b1334d1374b6adb97dfd28d9623c85a4`
- State: accepted DD-185 seven-volume stationary controller handoff
- Constant timestep: `0.125 s`
- Histories: endpoint = current = prior for inventories, internal energy, and PI memory
- Jacobians: dense central difference at `1e-5` and `5e-6` for BDF2; `1e-5` for backward Euler
- Required rank: `58 / 58`
- Nonlinear solve, accepted timestep, tuning, or trajectory: `False`

Commit this immutable contract before its one live execution. The audit may evaluate residuals and Jacobians only.
