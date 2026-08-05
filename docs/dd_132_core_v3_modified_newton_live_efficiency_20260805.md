# DD-132 Modified-Newton Live Efficiency Result

- Classification: `dd132_failed`
- Decision: `stop_modified_newton_live_path`
- Iterations: `[2, 2, 2]`
- Jacobian builds: `[1, 1, 1]`
- Worst residual: `1.761980e-09`
- Worst endpoint reproduction: `1.017993e-07`
- DWSIM calls: `3809`
- Wall clock: `2.281 s`

No Jacobian rebuild, fallback, retry, or trajectory was attempted.

## Decision Detail

Every gate passes except saved-endpoint reproduction. The half2 transformed
coordinate for `V[combined_reboiler_sump->stripping_tray]` differs from DD-130
by `1.017993e-7`, narrowly above the frozen `<1e-7` limit. The next-largest
coordinate difference is `9.947829e-8`. All physical inventory, energy, memory,
level, product, pressure, conservation, and direction checks pass.

The efficiency result is decisive: all three roots converge in two corrections
with one Jacobian each, using `3,809` DWSIM calls versus DD-130's `24,165`, a
reduction of approximately `84.2%`. The formal reproduction failure prohibits
a retry or trajectory. A zero-call physical-equivalence adjudication requires
separate authorization.
