# DD-090 PR Provider-Authority Contract

- Schema: `dd090-pr-provider-authority-contract-v1`
- Payload SHA-256: `5d32cae013549350133ad814e668d060fec59da6857400e97c4cc66d41822192`
- Preparation base commit: `ffa166e8e9f29d77c666867864a148ef5b496752`
- DD-089 result SHA-256: `323bda6043e70d99ee12f2f28be06dd124906dc1482f9c9c9a522429617493f8`
- Quantity rules: `11`

## Authority Table

| Quantity | Authority | Basis | Tolerance |
|---|---|---|---|
| `direct_phase_fugacity_residual` | DWSIM imposed-phase fugacity | declared liquid x and incipient vapor y | `direct_fugacity_residual_inf` |
| `direct_bubble_temperature` | DWSIM imposed-phase fugacity | fixed pressure and declared liquid x | `direct_fugacity_residual_inf` |
| `direct_incipient_vapor_composition` | DWSIM imposed-phase fugacity | fixed pressure and declared liquid x | `direct_fugacity_residual_inf` |
| `independent_pr_bubble_temperature` | independent parameter-aligned Peng-Robinson | same pressure, liquid x, constants, omega, and kij | `independent_pr_temperature_abs_F` |
| `independent_pr_incipient_vapor_composition` | independent parameter-aligned Peng-Robinson | same pressure, liquid x, constants, omega, and kij | `independent_pr_vapor_max_abs` |
| `tp_flash_phase_classification` | DWSIM TP flash | overall composition z at declared T and P | `classification/no scalar gate` |
| `tp_flash_phase_fraction` | DWSIM TP flash | overall composition z | `bubble_region_vapor_fraction` |
| `tp_flash_liquid_composition` | DWSIM TP flash | flash liquid phase x_flash | `classification/no scalar gate` |
| `tp_flash_vapor_composition` | DWSIM TP flash | flash vapor phase y_flash | `classification/no scalar gate` |
| `tp_flash_K_values` | DWSIM TP flash | K_flash = y_flash / x_flash | `flash_Kx_reconstruction_max_abs` |
| `tp_flash_lever_rule` | DWSIM TP flash | z = (1-beta)*x_flash + beta*y_flash | `flash_lever_rule_max_abs` |

## Frozen Policy

- Direct imposed-phase fugacity is the production equilibrium authority.
- Independent parameter-aligned PR is validation-only.
- TP flash owns phase classification, phase fraction, phase compositions, and lever-rule closure.
- Flash K-values are interpreted only on the flash phase bases.
- `normalize(K_flash*z)` is prohibited as a strict bubble-vapor gate when beta is nonzero.
- No fallback is permitted between direct fugacity and TP flash.
- No strict direct-y versus flash-y equality is required.

Execution performs a static audit against the immutable DD-089 evidence. No property call, column residual, solve, or dynamic integration is authorized.
