# Gani Stage Reconciliation Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\validation_gani_1986_debutanizer_model_topology_seed.xlsx`
- Runtime mode: `parity`
- Thermo: `clapeyron` `PR`
- Boundary states: `True`
- Vapor states: `True`
- Energy states: `True`
- Startup thermo conditioning iterations: `0`
- Condenser duty mode/value: `specified` / `-1.227e+07 Btu/h`

## Headline

- max |stage dM|: `0.000793664 lbmol/h` on stage `6`
- max |component dM|: `186.403 lbmol/h` on stage `28` component `Benzene`
- max |stage dE|: `3438.43 Btu/s` on stage `1`
- top pool material rate: `0.00044096 lbmol/h`
- bottom pool material rate: `8.81761e-05 lbmol/h`

## Worst Stage Material Residuals

- stage  6: dM=-0.001 lbmol/h (dL=-0.064, dV= 0.063, L 946.9->947.0, V 1469.1->1469.1, worst 1-pentene= 0.020)
- stage 22: dM=-0.001 lbmol/h (dL= 49.240, dV=-49.241, L 890.1->840.8, V 1363.0->1412.3, worst 1,3-butadiene= 0.493)
- stage  9: dM= 0.001 lbmol/h (dL=-0.075, dV= 0.076, L 947.1->947.2, V 1469.4->1469.3, worst 1-pentene= 0.105)
- stage 18: dM= 0.001 lbmol/h (dL= 4.502, dV=-4.502, L 942.1->937.6, V 1459.8->1464.3, worst 1,3-butadiene=-1.443)
- stage 14: dM=-0.001 lbmol/h (dL= 0.352, dV=-0.353, L 947.1->946.7, V 1468.9->1469.3, worst 1,3-butadiene=-4.645)
- stage 23: dM= 0.000 lbmol/h (dL=-552.691, dV= 552.692, L 840.8->1948.0, V 1361.2->1363.0, worst 1,3-butadiene= 0.087)
- stage 25: dM=-0.000 lbmol/h (dL= 24.965, dV=-24.965, L 1934.1->1909.2, V 1322.3->1347.3, worst 1,3-butadiene= 0.378)
- stage 16: dM=-0.000 lbmol/h (dL= 1.370, dV=-1.370, L 946.0->944.7, V 1466.8->1468.2, worst 1,3-butadiene=-3.215)
- stage 24: dM= 0.000 lbmol/h (dL= 13.903, dV=-13.903, L 1948.0->1934.1, V 1347.3->1361.2, worst 1,3-butadiene= 0.265)
- stage 11: dM=-0.000 lbmol/h (dL=-0.027, dV= 0.027, L 947.2->947.3, V 1469.5->1469.4, worst 1-pentene= 0.320)

## Worst Component Residuals

- stage 28 Benzene: dTotal=-186.403 lbmol/h (dL=-186.403, dV= 0.000)
- stage 26 Isobutene: dTotal=-186.297 lbmol/h (dL= 121.819, dV=-308.115)
- stage 26 1,3-butadiene: dTotal=-160.333 lbmol/h (dL= 95.200, dV=-255.532)
- stage 28 Isobutene: dTotal= 133.866 lbmol/h (dL= 133.866, dV= 0.000)
- stage 26 Benzene: dTotal= 130.763 lbmol/h (dL=-20.052, dV= 150.815)
- stage 28 1,3-butadiene: dTotal= 123.991 lbmol/h (dL= 123.991, dV= 0.000)
- stage 28 1-hexene: dTotal=-102.688 lbmol/h (dL=-102.688, dV= 0.000)
- stage 27 1-pentene: dTotal=-95.479 lbmol/h (dL=-56.157, dV=-39.322)
- stage 26 1-hexene: dTotal= 91.606 lbmol/h (dL=-21.386, dV= 112.993)
- stage 26 N-pentane: dTotal= 65.811 lbmol/h (dL=-55.032, dV= 120.842)
- stage 27 N-pentane: dTotal=-60.193 lbmol/h (dL=-54.184, dV=-6.009)
- stage 26 1-pentene: dTotal= 58.449 lbmol/h (dL=-81.973, dV= 140.422)

## Worst Energy Residuals

- stage  1: dE=-3438.433 Btu/s
- stage 28: dE= 2960.243 Btu/s
- stage 23: dE=-698.628 Btu/s
- stage 22: dE= 3.018 Btu/s
- stage 21: dE= 1.602 Btu/s
- stage 20: dE= 0.879 Btu/s
- stage 25: dE= 0.768 Btu/s
- stage 26: dE= 0.649 Btu/s

- Stage CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_model_topology_seed_audit_20260526\stage_reconciliation.csv`
- Component CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_model_topology_seed_audit_20260526\component_reconciliation.csv`
