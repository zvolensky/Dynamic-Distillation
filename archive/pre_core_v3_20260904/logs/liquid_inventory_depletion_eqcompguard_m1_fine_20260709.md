# Liquid Inventory Depletion Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_1300s_eqcompguard_m1_fine_20260709\column_profile_20260709_083905.csv`

## Summary

| Check | Value |
|---|---:|
| stages | 20 |
| stage rows | 5220 |
| minimum logged dt, s | 5 |
| minimum liquid limit, lbmol | 1 |
| update fraction limit | 0.25 |
| risky stages | 1 |
| passed | False |

## Interpretation

- `min_ML_lbmol` flags trays that approach an empty liquid state.
- `worst_update_fraction` estimates how large one logged liquid-inventory update is relative to the available liquid inventory.
- A low inventory plus a large update fraction can make explicit composition updates snap even when broader residual metrics look acceptable.

## Lowest Inventories

| stage_1based | min_ML_lbmol | time_s | below_limit | worst_update_fraction | worst_time_to_empty_s | worst_composition_step | component |
|---:|---:|---:|---:|---:|---:|---:|---|
| 12 | 0.208111 | 1200 | True | 0.211892 | 7.99381 | 0.972 | n_Butane |
| 15 | 30.0576 | 1300 | False | 0.00277797 | 1799.88 | 0.192073 | eq_n_Propane |
| 11 | 30.3428 | 0 | False | 0.00323109 | nan | 0.208998 | eq_n_Propane |
| 10 | 30.6704 | 0 | False | 0.0017287 | nan | 0.00834133 | n_Propane |
| 9 | 30.9079 | 0 | False | 0.000868066 | nan | 0.0126895 | n_Propane |
| 17 | 30.9645 | 1300 | False | 0.00407016 | 1228.45 | 0.154318 | eq_n_Propane |
| 8 | 31.1392 | 0 | False | 0.000492235 | nan | 0.0134556 | n_Propane |
| 18 | 31.3938 | 1300 | False | 0.00373565 | 1338.46 | 0.13222 | eq_n_Propane |
| 7 | 31.4403 | 0 | False | 0.000567796 | nan | 0.0120027 | n_Propane |
| 6 | 31.8916 | 0 | False | 0.00128445 | nan | 0.0145178 | n_Propane |

## Largest Inventory Update Fractions

| stage_1based | worst_update_fraction | time_s | dMLdt_total_lbmolps | min_ML_lbmol | update_limit_exceeded |
|---:|---:|---:|---:|---:|---:|
| 12 | 0.211892 | 1210 | -0.0423784 | 0.208111 | False |
| 2 | 0.00958683 | 5 | 0.073938 | 38.1926 | False |
| 3 | 0.00906026 | 5 | 0.0631142 | 34.5146 | False |
| 4 | 0.00594902 | 5 | 0.0400567 | 33.4663 | False |
| 17 | 0.00407016 | 1295 | -0.0253091 | 30.9645 | False |
| 18 | 0.00373565 | 1295 | -0.0235432 | 31.3938 | False |
| 11 | 0.00323109 | 5 | 0.0196716 | 30.3428 | False |
| 16 | 0.00318606 | 1295 | -0.0218324 | 34.1532 | False |
| 5 | 0.00303434 | 5 | 0.0197922 | 32.5148 | False |
| 15 | 0.00277797 | 1295 | -0.0167463 | 30.0576 | False |

## Largest Composition Steps

| stage_1based | composition_step | time_s | component | min_ML_lbmol |
|---:|---:|---:|---|---:|
| 12 | 0.972 | 1215 | n_Butane | 0.208111 |
| 11 | 0.208998 | 850 | eq_n_Propane | 30.3428 |
| 15 | 0.192073 | 775 | eq_n_Propane | 30.0576 |
| 16 | 0.177169 | 580 | eq_n_Propane | 34.1532 |
| 17 | 0.154318 | 340 | eq_n_Propane | 30.9645 |
| 18 | 0.13222 | 275 | eq_n_Propane | 31.3938 |
| 19 | 0.09983 | 190 | eq_n_Propane | 46.685 |
| 13 | 0.0275261 | 1255 | eq_n_Propane | 39.7028 |
| 4 | 0.0225636 | 160 | n_Propane | 33.4663 |
| 5 | 0.0209366 | 160 | n_Propane | 32.5148 |
