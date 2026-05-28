# Gani Stage Reconciliation Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_full_topology_pr_continue_300s_noeq_noVrelax\validation_gani_1986_debutanizer__restart_20260526_082510.xlsx`
- Runtime mode: `parity`
- Thermo: `clapeyron` `PR`
- Boundary states: `True`
- Vapor states: `True`
- Energy states: `True`
- Startup thermo conditioning iterations: `0`
- Condenser duty mode/value: `specified` / `-1.227e+07 Btu/h`

## Headline

- max |stage dM|: `1231.76 lbmol/h` on stage `28`
- max |component dM|: `824.092 lbmol/h` on stage `12` component `Isobutene`
- max |stage dE|: `816547 Btu/s` on stage `12`
- top pool material rate: `0.00044096 lbmol/h`
- bottom pool material rate: `-1231.76 lbmol/h`

## Worst Stage Material Residuals

- stage 28: dM= 1231.761 lbmol/h (dL= 1231.761, dV= 0.000, L 1818.6->586.8, V 1231.8->1231.8, worst Isobutene= 522.004)
- stage 22: dM=-0.001 lbmol/h (dL= 49.240, dV=-49.241, L 890.1->840.8, V 1363.0->1412.3, worst Isobutene=-374.060)
- stage  6: dM=-0.001 lbmol/h (dL=-0.064, dV= 0.063, L 946.9->947.0, V 1469.1->1469.1, worst Isobutene=-428.677)
- stage  9: dM= 0.001 lbmol/h (dL=-0.075, dV= 0.076, L 947.1->947.2, V 1469.4->1469.3, worst Isobutene= 620.058)
- stage 14: dM=-0.001 lbmol/h (dL= 0.352, dV=-0.353, L 947.1->946.7, V 1468.9->1469.3, worst Isobutene=-822.072)
- stage 18: dM= 0.001 lbmol/h (dL= 4.502, dV=-4.502, L 942.1->937.6, V 1459.8->1464.3, worst Isobutene=-807.391)
- stage 23: dM= 0.000 lbmol/h (dL=-552.691, dV= 552.692, L 840.8->1948.0, V 1361.2->1363.0, worst Isobutene=-366.609)
- stage 24: dM= 0.000 lbmol/h (dL= 13.903, dV=-13.903, L 1948.0->1934.1, V 1347.3->1361.2, worst Isobutene= 729.624)
- stage 25: dM=-0.000 lbmol/h (dL= 24.965, dV=-24.965, L 1934.1->1909.2, V 1322.3->1347.3, worst Isobutene=-712.311)
- stage  8: dM= 0.000 lbmol/h (dL=-0.080, dV= 0.080, L 947.0->947.1, V 1469.3->1469.2, worst Isobutene=-564.334)

## Worst Component Residuals

- stage 12 Isobutene: dTotal=-824.092 lbmol/h (dL=-17.694, dV=-806.398)
- stage 14 Isobutene: dTotal=-822.072 lbmol/h (dL=-15.792, dV=-806.279)
- stage 16 Isobutene: dTotal=-816.665 lbmol/h (dL=-11.081, dV=-805.584)
- stage 18 Isobutene: dTotal=-807.391 lbmol/h (dL=-4.328, dV=-803.063)
- stage 17 Isobutene: dTotal= 795.134 lbmol/h (dL=-7.928, dV= 803.063)
- stage 19 Isobutene: dTotal= 794.866 lbmol/h (dL=-0.143, dV= 795.009)
- stage 15 Isobutene: dTotal= 791.842 lbmol/h (dL=-13.742, dV= 805.584)
- stage 20 Isobutene: dTotal=-789.835 lbmol/h (dL= 5.175, dV=-795.009)
- stage 13 Isobutene: dTotal= 789.158 lbmol/h (dL=-17.122, dV= 806.279)
- stage 21 Isobutene: dTotal= 782.650 lbmol/h (dL= 13.312, dV= 769.339)
- stage 11 Isobutene: dTotal= 767.940 lbmol/h (dL=-17.579, dV= 785.518)
- stage 10 Isobutene: dTotal=-739.970 lbmol/h (dL=-16.936, dV=-723.034)

## Worst Energy Residuals

- stage 12: dE=-816547.313 Btu/s
- stage 14: dE=-816375.627 Btu/s
- stage 13: dE= 816101.806 Btu/s
- stage 15: dE= 815675.883 Btu/s
- stage 16: dE=-815461.434 Btu/s
- stage 17: dE= 814067.916 Btu/s
- stage 18: dE=-812376.129 Btu/s
- stage 19: dE= 808720.942 Btu/s

- Stage CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_full_topology_pr_steady_blocker_audit_20260526\stage_reconciliation.csv`
- Component CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_full_topology_pr_steady_blocker_audit_20260526\component_reconciliation.csv`
