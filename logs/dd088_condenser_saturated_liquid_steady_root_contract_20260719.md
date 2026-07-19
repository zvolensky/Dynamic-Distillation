# DD-088 Frozen Steady-Root Contract

- Schema: `dd088-core-v2-condenser-saturated-liquid-steady-root-contract-v1`
- Payload SHA-256: `df5e108636f35d9a2ccdd8fb423fdf9948575f86d86ef689c55e0da4b4188c9c`
- Preparation base commit: `bf614b3dcf2d2820dd17a3c9b093dd058b304bc8`
- DD-087 contract SHA-256: `0e7fcae93528105b87e4ceb3dc603f37b409d98106d86f1f88182efdb0b23fd0`
- Workbook SHA-256: `d1442928feb89bded76737614c0751e62bd4383a900b3c56bc243178080ca904`
- Coordinates/residuals: `40` / `40`
- Full-system solve attempted during preparation: `False`
- Dynamic integration attempted: `False`

## Frozen Starts

- `canonical_saturated_liquid_seed`: `40` coordinates, `||q||inf=0.000000e+00`
- `deterministic_dd087_perturbation`: `40` coordinates, `||q||inf=2.876773e-03`
- `independent_smooth_phase_stable_seed`: `40` coordinates, `||q||inf=4.088629e+00`

## Independent Start

- Drum composition: `[0.7940463225277119, 0.20594841570863484, 5.261763653048083e-06]`
- Bubble temperature: `126.089996991 F`
- Bubble residual: `4.218847e-15`
- Condenser duty: `-60462722.3956 BTU/h`

## Authorization

After this contract and implementation are committed and pushed, exactly one three-start execution is authorized. No alternate solver, continuation, restart, retuning, or dynamic integration is permitted.
