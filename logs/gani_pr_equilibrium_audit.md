# Gani PR Equilibrium Audit

- Excel: `validation_gani_1986_debutanizer.xlsx`
- Thermo: Clapeyron `PR`
- Stages: `28`
- Components: 1,3-butadiene, Isobutene, N-pentane, 1-pentene, 1-hexene, Benzene
- CSV: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\gani_pr_equilibrium_audit.csv`

## Headline Metrics

- max `abs(log(K_state/K_PR))`: `690.776`
- max `abs(y_seed - y_PR_at_seed_x)`: `0.13714`
- max `abs(sum(x*K_PR)-1)`: `0.121582`
- max `abs(sum(y/K_PR)-1)`: `0.5539`
- max `abs(HL_state-HL_PR)`: `nan Btu/lbmol`
- max `abs(HV_state-HV_PR)`: `nan Btu/lbmol`

## Worst K-Ratio Rows

- stage  2 1-pentene: K_state/K_PR=`0.00266379`, K_state=`0.0010561`, K_PR=`0.396464`
- stage  7 Benzene: K_state/K_PR=`5.51697`, K_state=`0.775`, K_PR=`0.140476`
- stage  8 Benzene: K_state/K_PR=`5.48785`, K_state=`0.807143`, K_PR=`0.147078`
- stage  6 Benzene: K_state/K_PR=`5.44117`, K_state=`0.73`, K_PR=`0.134162`
- stage  9 Benzene: K_state/K_PR=`5.39858`, K_state=`0.83125`, K_PR=`0.153976`
- stage 10 Benzene: K_state/K_PR=`5.27378`, K_state=`0.85`, K_PR=`0.161175`
- stage  5 Benzene: K_state/K_PR=`5.17045`, K_state=`0.6625`, K_PR=`0.128132`
- stage 11 Benzene: K_state/K_PR=`5.12802`, K_state=`0.865`, K_PR=`0.168681`
- stage 12 Benzene: K_state/K_PR=`4.97035`, K_state=`0.877273`, K_PR=`0.176501`
- stage 13 Benzene: K_state/K_PR=`4.80661`, K_state=`0.8875`, K_PR=`0.184642`
- stage 14 Benzene: K_state/K_PR=`4.64066`, K_state=`0.896154`, K_PR=`0.193109`
- stage  4 Benzene: K_state/K_PR=`4.49431`, K_state=`0.55`, K_PR=`0.122377`

## Worst Vapor-Composition Rows

- stage 26 Benzene: |y_seed-y_PR|=`0.13714`, y_seed=`0.209206`, y_PR=`0.0720667`
- stage 25 Benzene: |y_seed-y_PR|=`0.132176`, y_seed=`0.20036`, y_PR=`0.0681843`
- stage 24 Benzene: |y_seed-y_PR|=`0.127204`, y_seed=`0.191514`, y_PR=`0.06431`
- stage 23 Benzene: |y_seed-y_PR|=`0.122193`, y_seed=`0.182668`, y_PR=`0.0604754`
- stage 21 Isobutene: |y_seed-y_PR|=`0.118652`, y_seed=`0.227163`, y_PR=`0.345815`
- stage 22 Isobutene: |y_seed-y_PR|=`0.118617`, y_seed=`0.207742`, y_PR=`0.326358`
- stage 20 Isobutene: |y_seed-y_PR|=`0.117694`, y_seed=`0.246585`, y_PR=`0.364279`
- stage 23 Isobutene: |y_seed-y_PR|=`0.117471`, y_seed=`0.18832`, y_PR=`0.305791`
- stage 22 Benzene: |y_seed-y_PR|=`0.11712`, y_seed=`0.173823`, y_PR=`0.056703`
- stage 19 Isobutene: |y_seed-y_PR|=`0.115835`, y_seed=`0.266006`, y_PR=`0.381841`
- stage 24 Isobutene: |y_seed-y_PR|=`0.115056`, y_seed=`0.168899`, y_PR=`0.283955`
- stage 18 Isobutene: |y_seed-y_PR|=`0.113146`, y_seed=`0.285428`, y_PR=`0.398574`

