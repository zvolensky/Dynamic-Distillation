# ChemSep Warmer-Feed Parity Audit

- ChemSep file: `d:\Users\Thoma\Documents\Depropanizer_warmer_feed.sep`
- Workbook: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_depropanizer_chemsep_warmer_feed_pr76_source_20260531.xlsx`
- Condenser: 1 Condenser Total (Liquid product)
- Reboiler: 1 Reboiler Partial (Liquid product)
- Thermo: 2 K model EOS; 5 Cubic EOS Peng-Robinson 76
- Feed stage: 12
- Flow scaling: ChemSep basis values are treated as kmol/s and converted to lbmol/h.
- Duty scaling: ChemSep duties are treated as W and converted to Btu/h.

## Max Absolute Delta By Category

- duty: 0.0
- liquid_composition: 0.0
- profile: 4761.9848631933555
- spec: 0.0
- stream: 9.094947017729282e-13
- vapor_composition: 0.0

## Largest Differences

| Category | Item | ChemSep | Workbook | Delta | Units | Note |
|---|---:|---:|---:|---:|---|---|
| profile | stage_20_liquid_flow | 4761.98486 | 0 | -4761.98486 | lbmol/h | Likely intentional reboiler/bottoms topology mapping if workbook bottom-stage liquid flow is zero. |
| profile | stage_01_vapor_flow | 2380.99243 | 0 | -2380.99243 | lbmol/h | Likely intentional total-condenser topology mapping if workbook stage-1 vapor flow is zero. |
| profile | stage_19_liquid_flow | 12798.4693 | 12798.4693 | -5.45696821e-12 | lbmol/h |  |
| profile | stage_15_liquid_flow | 12506.2342 | 12506.2342 | 3.63797881e-12 | lbmol/h |  |
| profile | stage_16_liquid_flow | 12584.8307 | 12584.8307 | -3.63797881e-12 | lbmol/h |  |
| profile | stage_18_liquid_flow | 12760.6988 | 12760.6988 | -3.63797881e-12 | lbmol/h |  |
| profile | stage_12_liquid_flow | 12372.1922 | 12372.1922 | -1.8189894e-12 | lbmol/h |  |
| profile | stage_13_liquid_flow | 12402.6848 | 12402.6848 | 1.8189894e-12 | lbmol/h |  |
| profile | stage_14_liquid_flow | 12445.9474 | 12445.9474 | 1.8189894e-12 | lbmol/h |  |
| profile | stage_17_liquid_flow | 12675.9434 | 12675.9434 | -1.8189894e-12 | lbmol/h |  |
| stream | bottom_flow | 4761.98486 | 4761.98486 | 9.09494702e-13 | lbmol/h |  |
| profile | stage_04_vapor_flow | 7854.92737 | 7854.92737 | -9.09494702e-13 | lbmol/h |  |
| profile | stage_09_vapor_flow | 7586.03792 | 7586.03792 | 9.09494702e-13 | lbmol/h |  |
| stream | distillate_flow | 2380.99243 | 2380.99243 | 4.54747351e-13 | lbmol/h |  |
| profile | stage_04_temperature | 147.668 | 147.668 | -5.68434189e-14 | F |  |
| profile | stage_18_pressure | 230.769254 | 230.769254 | -5.68434189e-14 | psia |  |
| profile | stage_01_temperature | 117.932 | 117.932 | 4.26325641e-14 | F |  |
| profile | stage_02_temperature | 126.716 | 126.716 | 4.26325641e-14 | F |  |
| stream | feed_temperature | 174.9992 | 174.9992 | -2.84217094e-14 | F |  |
| stream | distillate_pressure_vs_chemsep_condenser | 218.439886 | 218.439886 | -2.84217094e-14 | psia | ChemSep top product uses condenser pressure; workbook appears to use top-stage pressure. |

## Interpretation Notes

- A large stage-1 vapor-flow difference is expected if the workbook intentionally maps the total condenser to zero vapor traffic in the dynamic model.
- A large bottom-stage liquid-flow difference is expected if the workbook intentionally maps the reboiler/bottoms outlet outside the tray liquid-flow profile.
- The distillate pressure difference is not just rounding: ChemSep reports a condenser/top-product pressure below the top tray pressure.
- Composition differences are small but real; they likely reflect the workbook being generated from a rounded/exported ChemSep table rather than this exact `.sep` result block.
