# Gani PR Equilibrium Audit

- Excel: `validation_gani_1986_debutanizer.xlsx`
- Thermo: Clapeyron `PR`
- Stages: `28`
- Components: 1,3-butadiene, Isobutene, N-pentane, 1-pentene, 1-hexene, Benzene
- CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_pr_equilibrium_audit_20260525_213242.csv`

## Headline Metrics

- max `abs(log(K_state/K_PR))`: `2.26266`
- max `abs(y_seed - y_PR_at_seed_x)`: `0.151331`
- max `abs(sum(x*K_PR)-1)`: `0.00272573`
- max `abs(sum(y/K_PR)-1)`: `2.74865e+283`
- max `abs(HL_state-HL_PR)`: `nan Btu/lbmol`
- max `abs(HV_state-HV_PR)`: `nan Btu/lbmol`

## Worst K-Ratio Rows

- stage  6 Benzene: K_state/K_PR=`0.104073`, K_state=`0.104073`, K_PR=`1`
- stage  7 Benzene: K_state/K_PR=`0.104197`, K_state=`0.104197`, K_PR=`1`
- stage  8 Benzene: K_state/K_PR=`0.104323`, K_state=`0.104323`, K_PR=`1`
- stage  9 Benzene: K_state/K_PR=`0.104453`, K_state=`0.104453`, K_PR=`1`
- stage 10 Benzene: K_state/K_PR=`0.104589`, K_state=`0.104589`, K_PR=`1`
- stage 11 Benzene: K_state/K_PR=`0.104735`, K_state=`0.104735`, K_PR=`1`
- stage 12 Benzene: K_state/K_PR=`0.104897`, K_state=`0.104897`, K_PR=`1`
- stage 13 Benzene: K_state/K_PR=`0.105091`, K_state=`0.105091`, K_PR=`1`
- stage  4 1-hexene: K_state/K_PR=`0.134578`, K_state=`0.134578`, K_PR=`1`
- stage  5 1-hexene: K_state/K_PR=`0.134743`, K_state=`0.134743`, K_PR=`1`
- stage  6 1-hexene: K_state/K_PR=`0.1349`, K_state=`0.1349`, K_PR=`1`
- stage  7 1-hexene: K_state/K_PR=`0.135052`, K_state=`0.135052`, K_PR=`1`

## Worst Vapor-Composition Rows

- stage 28 Benzene: |y_seed-y_PR|=`0.151331`, y_seed=`0.0912127`, y_PR=`0.242543`
- stage 27 Isobutene: |y_seed-y_PR|=`0.143918`, y_seed=`0.288483`, y_PR=`0.144566`
- stage 27 1,3-butadiene: |y_seed-y_PR|=`0.126184`, y_seed=`0.265568`, y_PR=`0.139384`
- stage 28 Isobutene: |y_seed-y_PR|=`0.108678`, y_seed=`0.179634`, y_PR=`0.0709559`
- stage 27 Benzene: |y_seed-y_PR|=`0.101781`, y_seed=`0.0382636`, y_PR=`0.140044`
- stage 28 1,3-butadiene: |y_seed-y_PR|=`0.100662`, y_seed=`0.171866`, y_PR=`0.0712045`
- stage 28 1-hexene: |y_seed-y_PR|=`0.0833667`, y_seed=`0.0843007`, y_PR=`0.167667`
- stage 27 1-hexene: |y_seed-y_PR|=`0.0713898`, y_seed=`0.0398119`, y_PR=`0.111202`
- stage 27 N-pentane: |y_seed-y_PR|=`0.0510586`, y_seed=`0.134207`, y_PR=`0.185266`
- stage 27 1-pentene: |y_seed-y_PR|=`0.0458725`, y_seed=`0.233666`, y_PR=`0.279538`
- stage 28 1-pentene: |y_seed-y_PR|=`0.0297047`, y_seed=`0.289124`, y_PR=`0.259419`
- stage 13 Isobutene: |y_seed-y_PR|=`0.0126201`, y_seed=`0.552661`, y_PR=`0.540041`

