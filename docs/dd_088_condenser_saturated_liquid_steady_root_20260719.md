# DD-088 Saturated-Liquid Steady-Root Result

## Decision

DD-088 formally fails its frozen acceptance contract.

All three starts found the same machine-precision, full-rank, conservative,
physically ordered algebraic root. The sole failed subgate is the
precommitted DWSIM TP-flash incipient-composition consistency limit:

```text
max|y_bubble - normalize(K*x)| = 1.46702e-5
frozen limit                   = 1.00000e-5
```

Per the hard stop, the solved-duty saturated-liquid five-volume steady
architecture is retired without a rerun, tolerance change, solver tuning,
duty sweep, wider bounds, partial-condenser variant, or dynamics.

## Frozen Execution

The full campaign definition was committed and pushed as `99c9973` before
execution. It fixed:

- all three 40-coordinate starts;
- transformed physical bounds;
- residual and physical comparison scales;
- solver and Jacobian settings;
- DWSIM TP consistency-floor tolerances;
- physical acceptance rules and hard stop.

The campaign executed exactly once and completed in `166.000 s`.

## Three-Start Result

| Start | Final scaled inf norm | nfev / njev | Worst condition | Pass |
|---|---:|---:|---:|---|
| Canonical saturated liquid | `3.89e-15` | `31 / 30` | `1.16247e3` | No |
| DD-087 perturbation | `3.33e-15` | `41 / 38` | `1.16247e3` | No |
| Independent phase-stable seed | `2.32e-14` | `48 / 43` | `1.16247e3` | No |

Each solver terminated successfully on `gtol`.

Physical endpoint differences are:

```text
canonical vs perturbation = 7.53e-11
canonical vs independent  = 7.53e-11
perturbation vs independent = 8.87e-15
```

All are below the `1e-7` common-root requirement.

## Common Root

The common endpoint is:

```text
T [F] =
[133.7133, 154.4222, 173.9246, 184.8240, 199.7405]

Q_C = -52.515728 MMBTU/h
D   = 2085.666 lbmol/h
B   = 5057.308 lbmol/h

L [lbmol/h] =
[5628.901, 12792.976, 12811.306]

V [lbmol/h] =
[7753.998, 7735.668, 7714.567, 8038.146]
```

The drum is `20.709 F` colder than the supplying rectifying stage. The
DD-085 hot-drum defect is absent.

The drum liquid and incipient vapor compositions are:

```text
x_D =
[0.70300120, 0.28360553, 0.01339327]

y_bubble =
[0.85127695, 0.14519622, 0.00352683]
```

## Passed Subgates

Every endpoint has:

- scaled residual below `2.4e-14`;
- rank `40/40` at `h=1e-5` and `h/2=5e-6`;
- local bubble rank `3/3`;
- condition about `1.16e3`;
- no zero row or column;
- no off-registry coupling;
- no active bound;
- negative condenser duty;
- ordered temperatures;
- positive amounts, products, and flows;
- normalized positive compositions;
- finite enthalpy, density, fugacity, and residual values;
- liquid heights below tray spacing;
- component and energy telescoping near `1e-16`;
- no clipping, projection, fallback, limiter, controller, or profile forcing.

The direct bubble-fugacity residual is approximately `1e-15`.

## Failed Subgate

The independent TP diagnostic at the common root is:

```text
sum(x*K)-1                     = 6.83403e-5  <= 1e-4
Rachford-Rice beta             = 6.43829e-4 <= 1e-3
max|y_bubble-normalize(K*x)|   = 1.46702e-5 > 1e-5
```

Thus:

- the state is not stable vapor;
- the direct equilibrium equations are solved tightly;
- two of three frozen TP consistency-floor checks pass;
- the incipient-composition cross-check misses by approximately `47%`.

This resembles the composition-dependent TP/forced-phase endpoint discrepancy
already identified during DD-087/DD-088 preparation. Nevertheless, the
threshold was frozen specifically to prevent post-result reinterpretation.
It cannot be relaxed after execution.

## DD-085 Comparison

| Quantity | DD-085 | DD-088 root |
|---|---:|---:|
| Drum temperature, F | `166.131` | `133.713` |
| Rectifying temperature, F | `162.898` | `154.422` |
| Drum phase diagnostic | Stable vapor | Near-bubble |
| Condenser duty, MMBTU/h | `-49.640` | `-52.516` |
| Top vapor flow, lbmol/h | `8770.682` | `8038.146` |
| Distillate, lbmol/h | `2818.202` | `2085.666` |
| Bottoms, lbmol/h | `4324.772` | `5057.308` |

DD-088 fixes the physical hot/stable-vapor condenser defect, but the frozen
cross-API phase-consistency contract still rejects the endpoint.

## Hard Stop

Do not create a DD-089 solver tuning, tolerance adjustment, duty sweep,
larger bound, restart, continuation, partial-condenser variant, or dynamic
integration campaign for this five-volume architecture.

Any future work must be a materially new architecture or a separately
justified provider/API validation program. The DD-088 endpoint may remain a
diagnostic artifact; it is not an accepted dynamic initializer.

Primary evidence:

- `logs/dd088_condenser_saturated_liquid_steady_root_contract_20260719.json`
- `logs/dd088_condenser_saturated_liquid_steady_root_20260719.json`
