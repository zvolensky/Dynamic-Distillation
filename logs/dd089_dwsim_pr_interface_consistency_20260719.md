# DD-089 DWSIM PR Interface-Consistency Result

- Classification: `repeatable_overall_vs_flash_liquid_composition_basis_effect`
- Contract commit: `fcf32378b0eaab84b8278d2d0e8d00e5fdd8c5f9`
- Wall clock: `15.569 s`
- Fresh-process maximum spread: `0.000000e+00`

## Preserved DD-088 State

- Legacy `y_direct` vs `normalize(K*z)`: `1.467021e-05`
- Direct bubble `y` vs TP-flash `y`: `4.280255e-05`
- TP-flash `y` vs `normalize(K*x_flash)`: `4.336809e-19`
- Composition-basis contribution: `5.747276e-05`
- Flash `x` vs overall `z`: `9.549809e-05`
- Rachford-Rice beta: `6.438286e-04`
- Lever-rule closure: `4.773959e-15`

## Independent PR

- Bubble temperature difference: `3.825286e-05 F`
- Vapor-composition maximum difference: `4.339660e-09`

## Authorization

DD-089 is a provider study only. DD-088 remains formally failed and retired. These findings may inform a prospective property contract for a materially new architecture; they do not authorize rerunning DD-088 or integrating dynamics.
