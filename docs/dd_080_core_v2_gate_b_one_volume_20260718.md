# DD-080 Core V2 Gate B One-Volume Closure

## Purpose

DD-080 tests one inventory-bearing equilibrium volume before any reduced
column is assembled. The volume is selected by its feed-tray role from the
mini8 workbook. Mini8 supplies components, nominal state, prescribed pressure,
liquid inventory scale, and geometry; it is not treated as solution truth.

## Formulation

The conserved state is:

```text
N_k, U
```

There is no vapor-holdup state. Liquid amount and composition are reconstructed
directly:

```text
NL = sum(N_k)
x_k = N_k / NL
```

The three algebraic unknowns are temperature and two independent vapor
composition coordinates. The `3 x 3` residual contains:

- one live DWSIM PR liquid internal-energy reconstruction;
- two independent liquid/vapor relative-fugacity equations.

The vapor coordinates use a smooth log-ratio representation. No composition
clipping, projection, phase relaxation, fixed-volume equation, or serialized
enthalpy is used.

## Live Property Interface

DD-080 adds a supported DWSIM phase-fugacity service through:

```text
CalcProp("fugacitycoefficient", "Mole", phase, ...)
```

This evaluates fugacity coefficients at the imposed liquid and vapor
compositions. It avoids treating a TP flash's overall-composition result as
the equilibrium relation for the inventory liquid composition.

## Static Results

The canonical state and four predefined perturbations all pass:

| Case | Temperature (F) | Maximum residual | Worst Jacobian condition | Pass |
|---|---:|---:|---:|---:|
| Canonical | `179.654000` | `1.13e-16` | `2.964` | Yes |
| +1% inventory | `179.654000` | `1.13e-16` | `2.937` | Yes |
| +0.5% internal energy | `180.254506` | `5.43e-13` | `2.974` | Yes |
| Propane-to-butane transfer | `179.750060` | `2.33e-14` | `2.962` | Yes |
| Combined bounded perturbation | `179.942382` | `1.72e-13` | `2.948` | Yes |

Every case:

- converges from the source-near, hot/light, and cool/heavy guesses;
- has numerical rank `3/3` at finite-difference steps `h` and `h/2`;
- has no zero Jacobian row or column;
- returns the same root within `1.28e-10 F` and `8.65e-14` vapor mole fraction;
- retains positive normalized phase compositions.

The canonical live-density geometry result is:

```text
NL                         51.062141 lbmol
rhoL                        0.510765 lbmol/ft3
liquid volume              99.971795 ft3
liquid height               0.589899 ft
over-weir head              0.451878 ft
derived Francis flow    16109.483026 lbmol/h
```

The liquid height remains below the `1.5 ft` tray spacing. Francis flow is
reported only as a derived diagnostic; it does not own a Gate B balance.

## Dynamic Results

The canonical no-disturbance case, inlet-composition step, inlet-enthalpy
step, and bounded combined case were integrated for `10 s` with BDF and
Radau. The short horizon is a local closure test, not a column settling run.

| Case | BDF/Radau difference | Component closure | Energy closure | Pass |
|---|---:|---:|---:|---:|
| No disturbance | `0` | `0` | `0` | Yes |
| Composition step | `5.34e-11` | `4.23e-16` | `1.10e-16` | Yes |
| Enthalpy step | `3.75e-9` | `1.69e-24` | `6.01e-17` | Yes |
| Combined bounded | `7.86e-10` | `4.60e-16` | `2.01e-16` | Yes |

All accepted output states pass the algebraic closure. Inventories,
temperature, and compositions remain physical without a fallback or
safeguard.

## Evidence

- `src/dynamic_distillation/core_v2/one_volume_property_gate_v1.py`
- `src/dynamic_distillation/pr_flash_backend_v1.py`
- `src/dynamic_distillation/thermo_provider_v1.py`
- `tools/audit_core_v2_gate_b_one_volume.py`
- `tests/test_core_v2_one_volume_property_gate_v1.py`
- `logs/dd080_core_v2_gate_b_one_volume_20260718.json`
- `logs/dd080_core_v2_gate_b_one_volume_20260718.md`
- `logs/dd080_core_v2_gate_b_one_volume_20260718_profiles.csv`

## Decision

DD-080 passes Gate B. Gate C is authorized for one five-volume,
prescribed-pressure model with Francis-only tray liquid-flow ownership and
prescribed section vapor rates.

This does not authorize energy-determined vapor traffic, production tray
count, a pressure-drop network, explicit vapor holdup, controllers, or use of
the legacy runtime as governing truth.
