# Gani PR Equilibrium Audit

- Excel: `validation_gani_1986_debutanizer.xlsx`
- Thermo: Clapeyron `PR`
- Stages: `28`
- Components: 1,3-butadiene, Isobutene, N-pentane, 1-pentene, 1-hexene, Benzene
- CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_pr_equilibrium_audit_after_profile_update.csv`

## Headline Metrics

- max `abs(log(K_state/K_PR))`: `1.21646`
- max `abs(y_seed - y_PR_at_seed_x)`: `1.11022e-16`
- max `abs(sum(x*K_PR)-1)`: `0.121582`
- max `abs(sum(y/K_PR)-1)`: `2.22045e-16`
- max `abs(HL_state-HL_PR)`: `nan Btu/lbmol`
- max `abs(HV_state-HV_PR)`: `nan Btu/lbmol`

## Worst K-Ratio Rows

- stage  2 Benzene: K_state/K_PR=`3.37523`, K_state=`0.376728`, K_PR=`0.111616`
- stage  2 1-hexene: K_state/K_PR=`3.08454`, K_state=`0.453006`, K_PR=`0.146863`
- stage  3 Benzene: K_state/K_PR=`2.39271`, K_state=`0.279671`, K_PR=`0.116885`
- stage  3 1-hexene: K_state/K_PR=`2.25856`, K_state=`0.349056`, K_PR=`0.154548`
- stage  2 N-pentane: K_state/K_PR=`2.12231`, K_state=`0.7055`, K_PR=`0.332421`
- stage  4 Benzene: K_state/K_PR=`2.06422`, K_state=`0.252613`, K_PR=`0.122377`
- stage  4 1-hexene: K_state/K_PR=`1.96829`, K_state=`0.319978`, K_PR=`0.162566`
- stage  2 1-pentene: K_state/K_PR=`1.91602`, K_state=`0.759632`, K_PR=`0.396464`
- stage  5 Benzene: K_state/K_PR=`1.88914`, K_state=`0.24206`, K_PR=`0.128132`
- stage  5 1-hexene: K_state/K_PR=`1.81014`, K_state=`0.309408`, K_PR=`0.170931`
- stage  6 Benzene: K_state/K_PR=`1.77399`, K_state=`0.238002`, K_PR=`0.134162`
- stage  3 N-pentane: K_state/K_PR=`1.75396`, K_state=`0.610043`, K_PR=`0.34781`

## Worst Vapor-Composition Rows

- stage  4 Isobutene: |y_seed-y_PR|=`1.11022e-16`, y_seed=`0.566307`, y_PR=`0.566307`
- stage 17 1-pentene: |y_seed-y_PR|=`6.93889e-17`, y_seed=`0.118337`, y_PR=`0.118337`
- stage  2 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.401311`, y_PR=`0.401311`
- stage  4 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.390625`, y_PR=`0.390625`
- stage  6 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.380988`, y_PR=`0.380988`
- stage 11 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.354431`, y_PR=`0.354431`
- stage 12 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.348492`, y_PR=`0.348492`
- stage 12 Isobutene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.48422`, y_PR=`0.48422`
- stage 13 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.342318`, y_PR=`0.342318`
- stage 13 Isobutene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.471523`, y_PR=`0.471523`
- stage 14 1,3-butadiene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.335902`, y_PR=`0.335902`
- stage 15 Isobutene: |y_seed-y_PR|=`5.55112e-17`, y_seed=`0.444327`, y_PR=`0.444327`

