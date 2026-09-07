# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_global_vapor_el_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.048367653 1/s`
- Worst absolute state rate: `1656.8816 per s`
- Max tray total material residual: `5255.3684 lbmol/h`
- Total state inventory residual: `110.47525 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.048367653 | 1.0994169 | 2 | n-Butane |
| `tray_L` | 0.019084226 | 0.20464479 | 2 | n-Butane |
| `tray_T_f` | 0.010671407 | 1.3629094 | 2 |  |
| `tray_EL_BTU` | 0.0085114714 | 1656.8816 | 2 |  |
| `top_V` | 0.0043566308 | 0.26582524 | 0 | n-Propane |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `top_L` | 0.0022502534 | 0.29705611 | 0 | n-Butane |
| `bottom_T_f` | 1.6735789e-08 | 3.7104965e-06 | 21 | n-Propane |
| `tray_EV_BTU` | 2.3592881e-15 | 2.3592881e-15 | 3 |  |
| `bottom_V` | 0 | 0 | 21 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.36726635 | 0.048367653 | 6.5932224 |
| 2 | `tray_V` | 2 | n-Propane | 1.0994169 | 0.044046074 | 23.960611 |
| 3 | `tray_V` | 17 | n-Propane | -0.30723305 | 0.027021721 | 10.369855 |
| 4 | `tray_V` | 18 | n-Propane | -0.25656921 | 0.026889779 | 8.5415143 |
| 5 | `tray_V` | 16 | n-Propane | -0.35188278 | 0.026549859 | 12.253659 |
| 6 | `tray_V` | 15 | n-Propane | -0.38133534 | 0.025264558 | 14.093687 |
| 7 | `tray_V` | 19 | n-Propane | -0.19941311 | 0.025174041 | 6.9213788 |
| 8 | `tray_V` | 14 | n-Propane | -0.40554572 | 0.024094557 | 15.831425 |
| 9 | `tray_V` | 5 | n-Butane | 0.21590273 | 0.023717503 | 8.1030968 |
| 10 | `tray_V` | 4 | n-Butane | 0.19817411 | 0.023688677 | 7.3657736 |
| 11 | `tray_V` | 6 | n-Butane | 0.22982995 | 0.023324591 | 8.8535469 |
| 12 | `tray_V` | 13 | n-Propane | -0.42714396 | 0.02315051 | 17.450737 |
| 13 | `tray_V` | 7 | n-Butane | 0.23874594 | 0.022648354 | 9.5414259 |
| 14 | `tray_V` | 3 | n-Butane | 0.17267242 | 0.022475869 | 6.6825692 |
| 15 | `tray_V` | 8 | n-Butane | 0.24330402 | 0.021829782 | 10.145508 |
| 16 | `tray_V` | 12 | n-Propane | -0.41278394 | 0.021068536 | 18.592436 |
| 17 | `tray_V` | 9 | n-Butane | 0.24279921 | 0.020856274 | 10.641543 |
| 18 | `tray_V` | 10 | n-Butane | 0.23862191 | 0.019864326 | 11.012585 |
| 19 | `tray_L` | 2 | n-Butane | -0.16218049 | 0.019084226 | 7.4981435 |
| 20 | `tray_V` | 11 | n-Butane | 0.23396751 | 0.019084221 | 11.259736 |
