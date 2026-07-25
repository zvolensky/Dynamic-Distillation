# DD-094 Core V3 Steady-Root Result

- Classification: `dd094_core_v3_steady_root_passed`
- Decision: `authorize_structural_dynamic_dae_contract_only`
- Contract commit: `52f132d`
- Mathematical contract SHA-256: `272890348b11b0164bb4ad506c97178a7565cf712677b51635d7e0c2feb01b93`
- Campaign executions: one
- Dynamic integration attempted: `False`

## Starts

| Start | nfev | Wall s | Worst scaled residual | Min bound distance | Pass |
|---|---:|---:|---:|---:|---|
| Canonical | 47 | 68.418 | `3.22e-15` | `0.182322` | Yes |
| DD-092 perturbation | 42 | 63.811 | `2.89e-15` | `0.182322` | Yes |
| Independent smooth | 55 | 51.292 | `7.43e-11` | `0.182322` | Yes |

Maximum pairwise normalized physical root difference is `2.47414e-10`
against the `1e-7` gate.

## Accepted Root

- Temperatures, F: `133.713293`, `154.422168`, `173.924644`,
  `184.824013`, `199.740489`
- Liquid amounts, lbmol: `1388.900000`, `32.859247`, `45.855669`,
  `54.424933`, `794.000000`
- Liquid flows, lbmol/h: `5628.901332`, `12792.976433`, `12811.305679`
- Vapor flows, lbmol/h: `7753.997711`, `7735.668466`, `7714.567365`,
  `8038.146033`
- Distillate: `2085.666033 lbmol/h`
- Bottoms: `5057.307967 lbmol/h`
- Condenser duty: `-52.515728 MMBTU/h`

All endpoint rank, spectrum, conservation, provider, phase, geometry,
temperature-ordering, and bound gates pass. The worst endpoint condition is
`1373.6911`; full/local ranks are `40/40` and `3/3`; the largest spectrum
step change is `4.21e-7`; TP beta is `6.43829e-4`; and independent PR agrees
within `3.83e-5 F` and `4.34e-9` composition.

DD-094 authorizes only drafting a structural dynamic-DAE contract. It does
not authorize mass-matrix implementation or dynamic integration.
