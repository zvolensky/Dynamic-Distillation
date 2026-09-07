# Liquid Inventory Depletion Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_m1_feedflash_20260709\column_profile_20260709_095126.csv`

## Summary

| Check | Value |
|---|---:|
| stages | 20 |
| stage rows | 1220 |
| minimum logged dt, s | 5 |
| minimum liquid limit, lbmol | 1 |
| update fraction limit | 0.25 |
| risky stages | 0 |
| passed | True |

## Interpretation

- `min_ML_lbmol` flags trays that approach an empty liquid state.
- `worst_update_fraction` estimates how large one logged liquid-inventory update is relative to the available liquid inventory.
- A low inventory plus a large update fraction can make explicit composition updates snap even when broader residual metrics look acceptable.

## Lowest Inventories

| stage_1based | min_ML_lbmol | time_s | below_limit | worst_update_fraction | worst_time_to_empty_s | worst_composition_step | component |
|---:|---:|---:|---:|---:|---:|---:|---|
| 11 | 30.3428 | 0 | False | 0.00323109 | nan | 0.0136498 | n_Propane |
| 10 | 30.6704 | 0 | False | 0.0017287 | nan | 0.00834133 | n_Propane |
| 9 | 30.9079 | 0 | False | 0.000868066 | nan | 0.0126895 | n_Propane |
| 8 | 31.1392 | 0 | False | 0.000492235 | nan | 0.0134556 | n_Propane |
| 7 | 31.4403 | 0 | False | 0.000567796 | nan | 0.0120027 | n_Propane |
| 6 | 31.8916 | 0 | False | 0.00128445 | nan | 0.0145178 | n_Propane |
| 5 | 32.5148 | 0 | False | 0.00303434 | nan | 0.0209366 | n_Propane |
| 4 | 33.4663 | 0 | False | 0.00594902 | nan | 0.0225636 | n_Propane |
| 3 | 34.5146 | 0 | False | 0.00906026 | nan | 0.0141252 | n_Propane |
| 2 | 38.1926 | 0 | False | 0.00958683 | nan | 0.0128595 | eq_n_Propane |

## Largest Inventory Update Fractions

| stage_1based | worst_update_fraction | time_s | dMLdt_total_lbmolps | min_ML_lbmol | update_limit_exceeded |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.00958683 | 5 | 0.073938 | 38.1926 | False |
| 3 | 0.00906026 | 5 | 0.0631142 | 34.5146 | False |
| 4 | 0.00594902 | 5 | 0.0400567 | 33.4663 | False |
| 12 | 0.00549504 | 295 | -0.0423784 | 38.3486 | False |
| 11 | 0.00323109 | 5 | 0.0196716 | 30.3428 | False |
| 5 | 0.00303434 | 5 | 0.0197922 | 32.5148 | False |
| 17 | 0.00224371 | 295 | -0.0253091 | 56.2736 | False |
| 18 | 0.00213816 | 295 | -0.0235432 | 54.9369 | False |
| 16 | 0.00194603 | 295 | -0.0218324 | 55.9856 | False |
| 15 | 0.00178579 | 295 | -0.0167463 | 46.8039 | False |

## Largest Composition Steps

| stage_1based | composition_step | time_s | component | min_ML_lbmol |
|---:|---:|---:|---|---:|
| 18 | 0.13222 | 275 | eq_n_Propane | 54.9369 |
| 19 | 0.09983 | 190 | eq_n_Propane | 57.1768 |
| 4 | 0.0225636 | 160 | n_Propane | 33.4663 |
| 5 | 0.0209366 | 160 | n_Propane | 32.5148 |
| 6 | 0.0145178 | 175 | n_Propane | 31.8916 |
| 3 | 0.0141252 | 175 | n_Propane | 34.5146 |
| 11 | 0.0136498 | 210 | n_Propane | 30.3428 |
| 8 | 0.0134556 | 270 | n_Propane | 31.1392 |
| 2 | 0.0128595 | 165 | eq_n_Propane | 38.1926 |
| 9 | 0.0126895 | 260 | n_Propane | 30.9079 |
