# Gani Stage Reconciliation Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\validation_gani_1986_debutanizer.xlsx`
- Runtime mode: `parity`
- Thermo: `clapeyron` `PR`
- Boundary states: `True`
- Vapor states: `True`
- Energy states: `True`
- Startup thermo conditioning iterations: `1`
- Condenser duty mode/value: `specified` / `-1.227e+07 Btu/h`

## Headline

- max |stage dM|: `1231.76 lbmol/h` on stage `28`
- max |component dM|: `356.131 lbmol/h` on stage `28` component `1-pentene`
- max |stage dE|: `1877.83 Btu/s` on stage `1`
- top pool material rate: `0.00044096 lbmol/h`
- bottom pool material rate: `-1231.76 lbmol/h`

## Worst Stage Material Residuals

- stage 28: dM= 1231.761 lbmol/h (dL= 1231.761, dV= 0.000, L 1818.6->586.8, V 1231.8->1231.8, worst 1-pentene= 356.131)
- stage 22: dM=-0.001 lbmol/h (dL= 49.240, dV=-49.241, L 890.1->840.8, V 1363.0->1412.3, worst Isobutene=-0.380)
- stage  6: dM=-0.001 lbmol/h (dL=-0.064, dV= 0.063, L 946.9->947.0, V 1469.1->1469.1, worst 1-pentene= 0.020)
- stage  9: dM= 0.001 lbmol/h (dL=-0.075, dV= 0.076, L 947.1->947.2, V 1469.4->1469.3, worst 1-pentene= 0.105)
- stage 18: dM= 0.001 lbmol/h (dL= 4.502, dV=-4.502, L 942.1->937.6, V 1459.8->1464.3, worst Isobutene=-0.188)
- stage 14: dM=-0.001 lbmol/h (dL= 0.352, dV=-0.353, L 947.1->946.7, V 1468.9->1469.3, worst Isobutene= 17.554)
- stage 23: dM= 0.000 lbmol/h (dL=-552.691, dV= 552.692, L 840.8->1948.0, V 1361.2->1363.0, worst Benzene=-0.338)
- stage 24: dM= 0.000 lbmol/h (dL= 13.903, dV=-13.903, L 1948.0->1934.1, V 1347.3->1361.2, worst Isobutene=-0.257)
- stage 25: dM=-0.000 lbmol/h (dL= 24.965, dV=-24.965, L 1934.1->1909.2, V 1322.3->1347.3, worst Isobutene=-0.790)
- stage 15: dM=-0.000 lbmol/h (dL= 0.719, dV=-0.719, L 946.7->946.0, V 1468.2->1468.9, worst 1,3-butadiene=-0.505)

## Worst Component Residuals

- stage 28 1-pentene: dTotal= 356.131 lbmol/h (dL= 356.131, dV= 0.000)
- stage 28 N-pentane: dTotal= 226.475 lbmol/h (dL= 226.475, dV= 0.000)
- stage 28 Isobutene: dTotal= 221.266 lbmol/h (dL= 221.266, dV= 0.000)
- stage 28 1,3-butadiene: dTotal= 211.698 lbmol/h (dL= 211.698, dV= 0.000)
- stage 26 Isobutene: dTotal=-186.573 lbmol/h (dL= 121.542, dV=-308.115)
- stage 26 1,3-butadiene: dTotal=-160.537 lbmol/h (dL= 94.995, dV=-255.532)
- stage 26 Benzene: dTotal= 130.898 lbmol/h (dL=-19.917, dV= 150.815)
- stage 28 Benzene: dTotal= 112.352 lbmol/h (dL= 112.352, dV= 0.000)
- stage 28 1-hexene: dTotal= 103.838 lbmol/h (dL= 103.838, dV= 0.000)
- stage 27 1-pentene: dTotal=-95.440 lbmol/h (dL=-56.118, dV=-39.322)
- stage 26 1-hexene: dTotal= 91.699 lbmol/h (dL=-21.294, dV= 112.993)
- stage 26 N-pentane: dTotal= 65.918 lbmol/h (dL=-54.924, dV= 120.842)

## Worst Energy Residuals

- stage  1: dE=-1877.831 Btu/s
- stage 23: dE= 1439.179 Btu/s
- stage 28: dE=-231.762 Btu/s
- stage 22: dE=-53.555 Btu/s
- stage 26: dE=-44.445 Btu/s
- stage 21: dE=-27.092 Btu/s
- stage 20: dE=-14.480 Btu/s
- stage 25: dE=-12.698 Btu/s

- Stage CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_stage_reconciliation_prvap_parity\stage_reconciliation.csv`
- Component CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_stage_reconciliation_prvap_parity\component_reconciliation.csv`
