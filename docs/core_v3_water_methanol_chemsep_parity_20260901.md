# Core V3 / ChemSep parity audit

- Result: `parity_not_established`
- Workbook: `water_methanol_template_10stage_chemsep_excess_enthalpy_p14p7_to_p17p7_geometry_20260713.xlsx`
- Bulk properties: `dwsim_unifac`
- Density only: `clapeyron_vtpr`

## What the repair changed

Core V3 now reconstructs the resident equilibrium vapor at both total terminals. The last ChemSep vapor row is a boundary placeholder, so it is no longer treated as an independent reboiler vapor state. No component-specific equation or constant was added.

- Bottom workbook temperature: `202.766000 F`
- Current-provider bottom bubble temperature: `212.561736 F`
- Change needed for current-provider equilibrium: `+9.795736 F`

## Independent closure results

- Interior VLE: maximum log-fugacity mismatch `0.175600` (`19.196%` as a fugacity-ratio error).
- Pressure: maximum equation mismatch `0.904746 psia`; required link coefficients span `10.115` to `22.923`.
- Liquid hydraulics: maximum Francis mismatch `6354.920 lbmol/h` (`45.708%`).
- Material: global component residual `0.000000 lbmol/h`; gate `True`.
- Energy: global residual `-2180914.412 BTU/h`; current properties require `Qc=-367080914.412 BTU/h` at the fixed ChemSep state.
- Levels from the same terminal molar holdups: top `49.920%`, bottom `52.359%` versus workbook nominal `50% / 50%`.

## Decision

The short dynamic run did not validate ChemSep parity; it validated a stationary root of the current model. The workbook product material balance itself closes, but its prescribed pressure profile, its VLE/enthalpy model, and the present free-pressure hydraulic equations are not one common stationary problem.

Do not fit a water-methanol-only correction. The next gate is to run two clearly separated modes: a prescribed-pressure steady-state parity check for thermodynamics and products, and a free-pressure dynamic initialization check for hydraulics. The bulk VLE/enthalpy provider must then be qualified against the ChemSep model before another long dynamic run.

## Pressure-link detail

| Link | Actual dP (psia) | Liquid head | Dry drop at K=40 | Residual | Required K |
|---|---:|---:|---:|---:|---:|
| combined_reboiler_sump->stripping_tray | 0.333333 | 0.000000 | 0.581659 | -0.248326 | 22.922931 |
| stripping_tray->feed_tray | 0.333333 | 0.032575 | 0.583003 | -0.282244 | 20.635147 |
| feed_tray->rectifying_volume_6 | 0.333333 | 0.028114 | 0.755756 | -0.450537 | 16.154389 |
| rectifying_volume_6->rectifying_volume_5 | 0.333333 | 0.006951 | 0.832459 | -0.506077 | 15.682814 |
| rectifying_volume_5->rectifying_volume_4 | 0.333333 | 0.009932 | 0.931190 | -0.607788 | 13.891978 |
| rectifying_volume_4->rectifying_volume_3 | 0.333333 | 0.016143 | 1.023271 | -0.706081 | 12.399056 |
| rectifying_volume_3->rectifying_volume_2 | 0.333333 | 0.021357 | 1.099095 | -0.787119 | 11.353921 |
| rectifying_volume_2->rectifying_volume_1 | 0.333333 | 0.024877 | 1.160263 | -0.851807 | 10.634008 |
| rectifying_volume_1->reflux_drum | 0.333333 | 0.027117 | 1.210963 | -0.904746 | 10.114824 |

## Liquid-hydraulic detail

| Volume | ChemSep L (lbmol/h) | Francis L (lbmol/h) | Residual | Relative |
|---|---:|---:|---:|---:|
| rectifying_volume_1 | 15733.800 | 15103.218 | 630.582 | 4.008% |
| rectifying_volume_2 | 15517.300 | 14214.256 | 1303.044 | 8.397% |
| rectifying_volume_3 | 15193.100 | 12809.913 | 2383.187 | 15.686% |
| rectifying_volume_4 | 14746.900 | 10723.651 | 4023.249 | 27.282% |
| rectifying_volume_5 | 14249.700 | 8300.298 | 5949.402 | 41.751% |
| rectifying_volume_6 | 13903.400 | 7548.480 | 6354.920 | 45.708% |
| feed_tray | 28948.700 | 24147.313 | 4801.387 | 16.586% |
| stripping_tray | 28977.500 | 30596.910 | -1619.410 | -5.589% |
