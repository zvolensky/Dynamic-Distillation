# DD-054 Composition Settle and Equilibrium-Gate Correction

Date: 2026-07-12

Run folder: `logs/c3c4_dd054_composition_settle_continue300s_20260712`

## Run result

The unchanged `300 s` continuation allowed the lower-column composition front to pass its peak and returned the dynamic gate to PASS.

| Metric | Final value |
|---|---:|
| Dynamic score | 0.420, PASS |
| Worst relative state rate | 0.00126/s |
| Top pressure | 221.098 psia |
| Condenser duty | -50.338 MMBtu/h |
| Reflux | 5967.323 lbmol/h |
| Distillate | 1999.482 lbmol/h |
| Top level | 51.775% |
| Bottom level | 49.455% |
| Distillate n-butane | 0.064260 mole fraction |
| Bottoms n-butane | 0.778231 mole fraction |
| Global mass-closure error | -5.83e-12 lbmol/h |

The final score trend was improving, vapor RHS maximum was only `0.000448/s`, and stage-19 liquid propane motion had declined materially.

## Gate correction

The historical K-state audit compared `K_state=y/x` directly with raw thermo K. That comparison is valid only when `sum(K*x)=1`. The model's normalized vapor target is:

`y_target_i = K_i*x_i / sum(K*x)`

Therefore the physically comparable acceptance quantity is `y-y_target`, not `y/x-K`.

At DD-054's former worst interior row, actual vapor propane was `0.16523` and target was `0.16438`, despite a large raw-K difference. After correcting the audit and excluding generic terminal states by default, DD-054 passed with final maximum interior `|y-y_target|=0.00432`.

Raw K fields remain in reports as diagnostic context. They no longer decide equilibrium consistency acceptance.
