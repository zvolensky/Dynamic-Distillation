# Gani Stage Reconciliation Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\validation_gani_1986_debutanizer__before_pr_vapor_profile_20260525_213353.xlsx`
- Runtime mode: `parity`
- Thermo: `clapeyron` `PR`
- Boundary states: `False`
- Vapor states: `False`
- Energy states: `True`
- Startup thermo conditioning iterations: `0`
- Condenser duty mode/value: `specified` / `-1.227e+07 Btu/h`

## Headline

- max |stage dM|: `0.000793664 lbmol/h` on stage `22`
- max |component dM|: `0.000436505 lbmol/h` on stage `6` component `Isobutene`
- max |stage dE|: `3438.43 Btu/s` on stage `1`
- top pool material rate: `nan lbmol/h`
- bottom pool material rate: `nan lbmol/h`

## Worst Stage Material Residuals

- stage 22: dM=-0.001 lbmol/h (dL=-0.001, dV= 0.000, L 890.1->840.8, V 1363.0->1412.3, worst Isobutene=-0.000)
- stage  6: dM=-0.001 lbmol/h (dL=-0.001, dV= 0.000, L 946.9->947.0, V 1469.1->1469.1, worst Isobutene=-0.000)
- stage  9: dM= 0.001 lbmol/h (dL= 0.001, dV= 0.000, L 947.1->947.2, V 1469.4->1469.3, worst Isobutene= 0.000)
- stage 18: dM= 0.001 lbmol/h (dL= 0.001, dV= 0.000, L 942.1->937.6, V 1459.8->1464.3, worst Isobutene= 0.000)
- stage 14: dM=-0.001 lbmol/h (dL=-0.001, dV= 0.000, L 947.1->946.7, V 1468.9->1469.3, worst Isobutene=-0.000)
- stage  1: dM= 0.000 lbmol/h (dL= 0.000, dV= 0.000, L 0.0->947.5, V 1469.7->0.0, worst Isobutene= 0.000)
- stage 23: dM= 0.000 lbmol/h (dL= 0.000, dV= 0.000, L 840.8->1948.0, V 1361.2->1363.0, worst Isobutene= 0.000)
- stage 28: dM= 0.000 lbmol/h (dL= 0.000, dV= 0.000, L 1818.6->586.8, V 1231.8->1231.8, worst 1-pentene= 0.000)
- stage 25: dM=-0.000 lbmol/h (dL=-0.000, dV= 0.000, L 1934.1->1909.2, V 1322.3->1347.3, worst Isobutene= 0.000)
- stage 19: dM= 0.000 lbmol/h (dL= 0.000, dV= 0.000, L 937.6->929.7, V 1451.9->1459.8, worst 1-pentene= 0.000)

## Worst Component Residuals

- stage  6 Isobutene: dTotal=-0.000 lbmol/h (dL=-0.000, dV= 0.000)
- stage  9 Isobutene: dTotal= 0.000 lbmol/h (dL= 0.000, dV= 0.000)
- stage 14 Isobutene: dTotal=-0.000 lbmol/h (dL=-0.000, dV= 0.000)
- stage 18 Isobutene: dTotal= 0.000 lbmol/h (dL= 0.000, dV= 0.000)
- stage 14 1,3-butadiene: dTotal=-0.000 lbmol/h (dL=-0.000, dV= 0.000)
- stage  9 1,3-butadiene: dTotal= 0.000 lbmol/h (dL= 0.000, dV= 0.000)
- stage  6 1,3-butadiene: dTotal=-0.000 lbmol/h (dL=-0.000, dV= 0.000)
- stage 22 Isobutene: dTotal=-0.000 lbmol/h (dL=-0.000, dV= 0.000)
- stage 18 1,3-butadiene: dTotal= 0.000 lbmol/h (dL= 0.000, dV= 0.000)
- stage 22 1,3-butadiene: dTotal=-0.000 lbmol/h (dL=-0.000, dV= 0.000)
- stage  1 Isobutene: dTotal= 0.000 lbmol/h (dL= 0.000, dV= 0.000)
- stage  1 1,3-butadiene: dTotal= 0.000 lbmol/h (dL= 0.000, dV= 0.000)

## Worst Energy Residuals

- stage  1: dE=-3438.433 Btu/s
- stage 28: dE= 3099.219 Btu/s
- stage 23: dE=-699.591 Btu/s
- stage 27: dE=-6.051 Btu/s
- stage 26: dE=-3.539 Btu/s
- stage 25: dE=-1.831 Btu/s
- stage 24: dE=-0.916 Btu/s
- stage 22: dE= 0.220 Btu/s

- Stage CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_stage_reconciliation_chemsepY_source_noV_noB\stage_reconciliation.csv`
- Component CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_stage_reconciliation_chemsepY_source_noV_noB\component_reconciliation.csv`
