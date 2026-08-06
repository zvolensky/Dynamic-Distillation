# DD-154 Zero-Call Pool-Renewal Cadence Result

## Decision

DD-154 fails only the precommitted meaningful-improvement gate. The nominal model selects a renewal cadence of `300` roots, but projects only an `11.86%` wall-time improvement over the measured persistent-pool baseline. This is below the required `20%`; pool renewal is therefore not authorized.

- Contract commit: `2950f3d`
- Contract payload SHA-256: `a45f55bc28be6d02f9cc6280af899b358be27fe557ca4bee1dae1e69268ec8bd`
- Classification: `cadence_model_invalid`
- Decision: `retain_persistent_pool_without_trajectory_extension`
- DWSIM/provider/model calls: `0`
- Analysis wall: `0.962143 s`

## Measured Inputs

| Input | Value |
|---|---:|
| Fresh coarse Jacobian | `0.229702 s` |
| Fresh refined Jacobian | `0.225050 s` |
| Coarse aging slope | `0.000200927 s/root` |
| Refined aging slope | `0.000303429 s/root` |
| Complete pool lifecycle overhead | `12.713885 s/pool` |
| Fixed trajectory non-Jacobian wall | `60.215191 s` |
| Additive baseline calibration | `81.324685 s` |

The additive calibration makes the cadence-900 model reproduce DD-151's measured `476.349405 s` wall exactly. It is held constant for every candidate.

## Nominal Projection

| Renewal cadence (roots) | Pools | Jacobian (s) | Pool lifecycle (s) | Projected total (s) |
|---:|---:|---:|---:|---:|
| 60 | 15 | 211.090 | 190.708 | 543.338 |
| 120 | 8 | 217.998 | 101.711 | 461.249 |
| 180 | 5 | 225.999 | 63.569 | 431.108 |
| 240 | 4 | 231.815 | 50.856 | 424.210 |
| **300** | **3** | **240.170** | **38.142** | **419.851** |
| 360 | 3 | 243.447 | 38.142 | 423.128 |
| 450 | 2 | 260.651 | 25.428 | 427.619 |
| 900 | 1 | 322.096 | 12.714 | 476.349 |

The `0.75x`, nominal, and `1.25x` slope scenarios all select `300` roots, so the location of the minimum is robust. The projected gain is not large enough to justify implementation risk or another trajectory campaign.

## Gate Record

- Source integrity: pass
- Exact cadence-900 baseline calibration: pass
- Selected cadence within `120..450`: pass
- At least `20%` projected improvement: **fail** (`11.86%`)
- Slope-uncertainty selection bounded: pass
- Zero model/provider calls: pass
- Analysis wall below `120 s`: pass

## Meaning

DD-153 proved that long-lived workers become slower, but DD-154 shows that destroying and recreating the complete pool is not an efficient remedy under the measured startup and shutdown cost. The next efficiency investigation, if separately authorized, should target a cheaper in-worker reset of the responsible provider/cache/backend state while retaining the existing processes. No renewal implementation or trajectory extension is authorized by this result.
