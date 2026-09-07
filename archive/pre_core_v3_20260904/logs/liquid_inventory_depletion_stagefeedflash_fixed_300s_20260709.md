# Liquid Inventory Depletion Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_stagefeedflash_fixed_300s_20260709\column_profile_20260709_100852.csv`

## Summary

| Check | Value |
|---|---:|
| stages | 20 |
| stage rows | 1220 |
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
| 12 | 0.155514 | 200 | True | 5.17229 | 0.298617 | 1 | n_Propane |
| 11 | 30.3428 | 0 | False | 0.00323109 | nan | 0.00746407 | eq_n_Propane |
| 10 | 30.6704 | 0 | False | 0.0017287 | nan | 0.0077017 | n_Propane |
| 9 | 30.9079 | 0 | False | 0.000868066 | nan | 0.00866794 | eq_n_Butane |
| 8 | 31.1392 | 0 | False | 0.000492235 | nan | 0.00954771 | n_Propane |
| 7 | 31.4403 | 0 | False | 0.000567796 | nan | 0.0128314 | eq_n_Butane |
| 6 | 31.8916 | 0 | False | 0.00128445 | nan | 0.0176044 | n_Butane |
| 5 | 32.5148 | 0 | False | 0.00303434 | nan | 0.0188088 | n_Propane |
| 4 | 33.4663 | 0 | False | 0.00594902 | nan | 0.0250004 | n_Propane |
| 3 | 34.5146 | 0 | False | 0.00906026 | nan | 0.0271933 | n_Propane |

## Largest Inventory Update Fractions

| stage_1based | worst_update_fraction | time_s | dMLdt_total_lbmolps | min_ML_lbmol | update_limit_exceeded |
|---:|---:|---:|---:|---:|---:|
| 12 | 5.17229 | 255 | -1.03446 | 0.155514 | True |
| 2 | 0.00958683 | 5 | 0.073938 | 38.1926 | False |
| 3 | 0.00906026 | 5 | 0.0631142 | 34.5146 | False |
| 4 | 0.00594902 | 5 | 0.0400567 | 33.4663 | False |
| 11 | 0.00323109 | 5 | 0.0196716 | 30.3428 | False |
| 5 | 0.00303434 | 5 | 0.0197922 | 32.5148 | False |
| 17 | 0.00224371 | 295 | -0.0253091 | 56.2736 | False |
| 18 | 0.00213816 | 295 | -0.0235432 | 54.9369 | False |
| 16 | 0.00194603 | 295 | -0.0218324 | 55.9856 | False |
| 15 | 0.00178579 | 295 | -0.0167463 | 46.8039 | False |

## Largest Composition Steps

| stage_1based | composition_step | time_s | component | min_ML_lbmol |
|---:|---:|---:|---|---:|
| 12 | 1 | 205 | n_Propane | 0.155514 |
| 16 | 0.169329 | 255 | eq_n_Propane | 55.9856 |
| 15 | 0.164489 | 225 | eq_n_Propane | 46.8039 |
| 14 | 0.156852 | 210 | eq_n_Propane | 46.7826 |
| 17 | 0.155545 | 255 | eq_n_Propane | 56.2736 |
| 18 | 0.131419 | 245 | eq_n_Propane | 54.9369 |
| 19 | 0.104751 | 200 | eq_n_Propane | 57.1768 |
| 13 | 0.0592144 | 205 | n_Propane | 48.1729 |
| 3 | 0.0271933 | 165 | n_Propane | 34.5146 |
| 4 | 0.0250004 | 160 | n_Propane | 33.4663 |
