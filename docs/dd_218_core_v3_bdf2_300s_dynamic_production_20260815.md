# DD-218 Five-Minute Dynamic Production Result

- Classification: `five_minute_dynamic_production_failed`
- Decision: `retain_dd217_60s_production_boundary`
- Completed roots: `1200` / `1200`
- Worst residual / condition: `5.344218e-12` / `7.934670e+06`
- DD-217 prefix maximum difference: `0.000000e+00`
- Startup / active / shutdown / total: `2.851` / `417.543` / `38.418` / `458.846 s`
- Simulated/active-wall ratio: `0.7185`
- Matrices / logical calls: `3217` / `3891028`
- Saved samples: `61`; full step SHA-256: `1f2a67d82506a56a73f2690bd01b095ec46632be4ab34dd2649cf7959fef2a1e`
- Retry, tuning, alternate grid, or fallback: `False`

## Formal Result

DD-218 completes all `1200/1200` roots and fails exactly one frozen campaign
gate: `response`. The legacy short-horizon policy requires total inventory to
be strictly increasing at every accepted step. Over five minutes the terminal
level controllers eventually reverse the accumulation, so that boolean is
false.

Every other gate passes. Worst residual is `5.344218e-12`, worst condition is
`7.934670e+06`, and maximum component/energy conservation errors are
`2.319120e-12/6.882451e-12`. The first 240 roots reproduce DD-217 exactly with
maximum difference `0.0`. All 3,217 Jacobians use eight workers; provider
ownership and all 3,891,028 logical calls pass without fallback.

## Timing

- Startup: `2.851098 s`
- Active trajectory: `417.543182 s`
- Final shutdown: `38.418092 s`
- Complete session: `458.845943 s`
- Simulated/active-wall ratio: `0.7185`
- Simulated/session-wall ratio: `0.6538`

All timing and attribution gates pass. Longer execution improves average
throughput because startup and nonlinear warm-up are amortized.

## Observed Controlled Response

Global component-inventory recurrence closes to `1.432099e-11 lbmol`, and the
total relative error is `6.153598e-11`. Sampled total inventory rises from
`2404.021619 lbmol`, peaks at `2404.288656 lbmol` near `280 s`, then declines
for the final four five-second samples to `2404.288049 lbmol` at `300 s`.
Bottoms withdrawal rises monotonically from `4922.0217` to `4929.4047 lbmol/h`,
consistent with corrective bottom-level action. Both terminal levels remain
physical.

DD-218 remains formally failed and is not rerun or reclassified. DD-219 is a
separately frozen, zero-call adjudication of whether this bounded late reversal
is the correct controlled long-horizon response rather than a defect.
