# DD-198 Controlled BDF2 Moving-Step Contract

- Payload SHA-256: `0230191bd724408c7cc2ca725abd12397d3baea15c8217e616008ca5b8910364`
- Preparation base commit: `f604b80e25968955b40cef30a7b99b496b9010f0`
- Disturbance: unchanged DD-187 `+0.1%` feed-rate and feed-enthalpy step
- Startup history: DD-185 stationary state at `t=0`, accepted DD-187 backward-Euler half-step at `t=0.125 s`
- BDF2 endpoint: one fixed `0.125 s` step to `t=0.25 s`
- Reference: accepted DD-187 second backward-Euler half-step
- Accuracy gate: BDF2 inventory must be closer than refined backward Euler to the DD-187 Richardson inventory estimate
- Solver/settings/controllers/product references: unchanged
- Retry, alternate step, tuning, or trajectory: `False`

Commit this immutable contract before its one live execution.
