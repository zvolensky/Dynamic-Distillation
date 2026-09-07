# ChemSep Warmer-Feed Parity Audit

- ChemSep file: `d:\Users\Thoma\Documents\Depropanizer_warmer_feed.sep`
- Workbook: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_20260526.xlsx`
- Condenser: 1 Condenser Total (Liquid product)
- Reboiler: 1 Reboiler Partial (Liquid product)
- Thermo: 2 K model EOS; 5 Cubic EOS Peng-Robinson 76
- Feed stage: 12
- Flow scaling: ChemSep basis values are treated as kmol/s and converted to lbmol/h.
- Duty scaling: ChemSep duties are treated as W and converted to Btu/h.

## Max Absolute Delta By Category

- duty: 190424.89924059808
- liquid_composition: 0.00176300439999999
- profile: 4761.9848631933555
- spec: 0.0
- stream: 2.0001135819091758
- vapor_composition: 0.0014884942000000234

## Largest Differences

| Category | Item | ChemSep | Workbook | Delta | Units | Note |
|---|---:|---:|---:|---:|---|---|
| duty | condenser_duty | -49830424.9 | -49640000 | 190424.899 | Btu/h |  |
| duty | reboiler_duty | 54844297.7 | 54706000 | -138297.671 | Btu/h |  |
| profile | stage_20_liquid_flow | 4761.98486 | 0 | -4761.98486 | lbmol/h | Likely intentional reboiler/bottoms topology mapping if workbook bottom-stage liquid flow is zero. |
| profile | stage_01_vapor_flow | 2380.99243 | 0 | -2380.99243 | lbmol/h | Likely intentional total-condenser topology mapping if workbook stage-1 vapor flow is zero. |
| profile | stage_03_vapor_flow | 8082.13595 | 8057.4 | -24.7359495 | lbmol/h |  |
| profile | stage_02_liquid_flow | 5701.1459 | 5676.41 | -24.7358989 | lbmol/h |  |
| profile | stage_04_vapor_flow | 7854.92737 | 7831.59 | -23.3373657 | lbmol/h |  |
| profile | stage_03_liquid_flow | 5473.93493 | 5450.6 | -23.3349341 | lbmol/h |  |
| profile | stage_19_vapor_flow | 7998.71391 | 7976.47 | -22.2439113 | lbmol/h |  |
| profile | stage_18_liquid_flow | 12760.6988 | 12738.5 | -22.1987745 | lbmol/h |  |
| profile | stage_17_liquid_flow | 12675.9434 | 12653.8 | -22.1433806 | lbmol/h |  |
| profile | stage_18_vapor_flow | 7913.95852 | 7891.85 | -22.1085174 | lbmol/h |  |
| profile | stage_19_liquid_flow | 12798.4693 | 12776.5 | -21.9692511 | lbmol/h |  |
| profile | stage_20_vapor_flow | 8036.48439 | 8014.56 | -21.924388 | lbmol/h |  |
| profile | stage_05_vapor_flow | 7710.72335 | 7689.05 | -21.6733528 | lbmol/h |  |
| profile | stage_04_liquid_flow | 5329.73092 | 5308.06 | -21.6709212 | lbmol/h |  |
| profile | stage_17_vapor_flow | 7822.84587 | 7801.2 | -21.6458737 | lbmol/h |  |
| profile | stage_16_liquid_flow | 12584.8307 | 12563.2 | -21.6307369 | lbmol/h |  |
| profile | stage_15_liquid_flow | 12506.2342 | 12485.2 | -21.0341767 | lbmol/h |  |
| profile | stage_16_vapor_flow | 7744.24693 | 7723.22 | -21.0269325 | lbmol/h |  |

## Interpretation Notes

- A large stage-1 vapor-flow difference is expected if the workbook intentionally maps the total condenser to zero vapor traffic in the dynamic model.
- A large bottom-stage liquid-flow difference is expected if the workbook intentionally maps the reboiler/bottoms outlet outside the tray liquid-flow profile.
- The distillate pressure difference is not just rounding: ChemSep reports a condenser/top-product pressure below the top tray pressure.
- Composition differences are small but real; they likely reflect the workbook being generated from a rounded/exported ChemSep table rather than this exact `.sep` result block.
