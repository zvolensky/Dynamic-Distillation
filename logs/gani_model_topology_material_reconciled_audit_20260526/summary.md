# Gani Stage Reconciliation Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\validation_gani_1986_debutanizer_model_topology_material_reconciled.xlsx`
- Runtime mode: `parity`
- Thermo: `clapeyron` `PR`
- Boundary states: `True`
- Vapor states: `True`
- Energy states: `True`
- Startup thermo conditioning iterations: `0`
- Condenser duty mode/value: `specified` / `-1.227e+07 Btu/h`

## Headline

- max |stage dM|: `0.000793664 lbmol/h` on stage `6`
- max |component dM|: `17.6392 lbmol/h` on stage `1` component `Isobutene`
- max |stage dE|: `3438.43 Btu/s` on stage `1`
- top pool material rate: `0.00044096 lbmol/h`
- bottom pool material rate: `8.81761e-05 lbmol/h`

## Worst Stage Material Residuals

- stage  6: dM=-0.001 lbmol/h (dL=-0.064, dV= 0.063, L 946.9->947.0, V 1469.1->1469.1, worst Isobutene=-0.000)
- stage 22: dM=-0.001 lbmol/h (dL= 49.240, dV=-49.241, L 890.1->840.8, V 1363.0->1412.3, worst Isobutene=-0.000)
- stage 18: dM= 0.001 lbmol/h (dL= 4.502, dV=-4.502, L 942.1->937.6, V 1459.8->1464.3, worst Isobutene= 0.000)
- stage  9: dM= 0.001 lbmol/h (dL=-0.075, dV= 0.076, L 947.1->947.2, V 1469.4->1469.3, worst Isobutene= 0.000)
- stage 14: dM=-0.001 lbmol/h (dL= 0.352, dV=-0.353, L 947.1->946.7, V 1468.9->1469.3, worst Isobutene=-0.000)
- stage 23: dM= 0.000 lbmol/h (dL=-552.691, dV= 552.692, L 840.8->1948.0, V 1361.2->1363.0, worst Isobutene= 0.000)
- stage 25: dM=-0.000 lbmol/h (dL= 24.965, dV=-24.965, L 1934.1->1909.2, V 1322.3->1347.3, worst Isobutene=-0.000)
- stage 24: dM= 0.000 lbmol/h (dL= 13.903, dV=-13.903, L 1948.0->1934.1, V 1347.3->1361.2, worst Isobutene= 0.000)
- stage 16: dM=-0.000 lbmol/h (dL= 1.370, dV=-1.370, L 946.0->944.7, V 1466.8->1468.2, worst 1,3-butadiene=-0.000)
- stage 10: dM= 0.000 lbmol/h (dL=-0.060, dV= 0.060, L 947.2->947.2, V 1469.4->1469.4, worst 1,3-butadiene= 0.000)

## Worst Component Residuals

- stage  1 Isobutene: dTotal=-17.639 lbmol/h (dL=-17.639, dV= 0.000)
- stage  1 1,3-butadiene: dTotal= 17.637 lbmol/h (dL= 17.637, dV= 0.000)
- stage  1 1-pentene: dTotal= 0.002 lbmol/h (dL= 0.002, dV= 0.000)
- stage 14 Isobutene: dTotal=-0.000 lbmol/h (dL=-3.786, dV= 3.786)
- stage 18 Isobutene: dTotal= 0.000 lbmol/h (dL= 6.916, dV=-6.915)
- stage  6 Isobutene: dTotal=-0.000 lbmol/h (dL= 1.995, dV=-1.995)
- stage  9 Isobutene: dTotal= 0.000 lbmol/h (dL= 0.581, dV=-0.581)
- stage  9 1,3-butadiene: dTotal= 0.000 lbmol/h (dL=-0.476, dV= 0.476)
- stage  6 1,3-butadiene: dTotal=-0.000 lbmol/h (dL=-2.026, dV= 2.026)
- stage 14 1,3-butadiene: dTotal=-0.000 lbmol/h (dL= 5.311, dV=-5.311)
- stage 22 Isobutene: dTotal=-0.000 lbmol/h (dL= 63.985, dV=-63.986)
- stage 18 1,3-butadiene: dTotal= 0.000 lbmol/h (dL= 8.818, dV=-8.818)

## Worst Energy Residuals

- stage  1: dE=-3438.433 Btu/s
- stage 28: dE= 2960.243 Btu/s
- stage 23: dE=-698.628 Btu/s
- stage 22: dE= 3.018 Btu/s
- stage 21: dE= 1.602 Btu/s
- stage 20: dE= 0.879 Btu/s
- stage 25: dE= 0.768 Btu/s
- stage 26: dE= 0.649 Btu/s

- Stage CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_model_topology_material_reconciled_audit_20260526\stage_reconciliation.csv`
- Component CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_model_topology_material_reconciled_audit_20260526\component_reconciliation.csv`
