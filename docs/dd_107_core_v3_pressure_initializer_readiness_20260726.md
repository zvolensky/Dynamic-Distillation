# DD-107 Core V3 Pressure Initializer Readiness

## Decision

Stop DD-106 before a live numerical contract or DWSIM execution. Its
property-free equality and KKT ledgers remain structurally valid, but the
continuous energy-rate equation needed by its nonzero-rate objective is not
defined for moving algebraic pressure.

No property call, constrained optimizer, timestep, trajectory, controller, or
integration was attempted.

## The Missing Equation

DD-106 contains:

- 15 component inventories `N[j,k]`;
- 15 potentially nonzero rates `dN[j,k]/dt`;
- four moving algebraic lower pressures;
- five energy balances;
- no independent `U[j]` states or `dU[j]/dt` rates;
- no pressure rates.

Its inherited DD-104 storage statement is exact only in discrete form:

```text
U_next - U_previous
```

That is correct inside a specified backward-Euler step. DD-106 intentionally
has no timestep, so this expression cannot define continuous `dU/dt`.

DD-096's storage gradient is also unavailable: it was derived on the
fixed-pressure saturation manifold. Reusing it after pressure becomes
algebraic would omit the energy change caused by pressure and temperature
motion, precisely the inconsistency DD-105 was designed to avoid.

## Why The Objective Does Not Rescue It

DD-106 minimizes inventory rates but does not constrain them to zero. A
minimum-rate solution may therefore retain nonzero `dN/dt`. Every such trial
requires a physically defined `dU/dt` in the five exact energy balances.
Without that definition, objective weights or a nonlinear solver cannot make
the formulation complete.

The readiness ledger is:

```text
component-inventory states           15
component-inventory rates            15
independent energy states             0
energy-rate variables                 0
algebraic pressures                    4
pressure-rate variables                0
energy balances                        5
continuous pressure-aware dU/dt     absent
live numerical readiness            false
```

## Prohibited Shortcuts

- Do not reuse the DD-096 fixed-pressure storage gradient.
- Do not introduce a hidden initializer timestep.
- Do not execute the DD-106 constrained optimizer.
- Do not tune objective weights, scales, or solver settings around the gap.

## Next Authorized Increment

Define one property-free conserved-`N/U`, algebraic-pressure DAE ownership
audit. Its purpose is to determine whether adding five independent liquid
internal-energy coordinates and rates, together with five constitutive
storage equations, creates a square, conservative, full-rank system without
adding pressure rates or a second vapor-flow owner.

This is an architectural correction, not a revival of checkpoint repair. A
structural failure would stop that successor before live properties. A pass
would authorize only a separately frozen numerical rank/readiness audit.

Primary evidence:

- `logs/dd107_core_v3_pressure_initializer_readiness_20260726.json`
- `src/dynamic_distillation/core_v3/pressure_initializer_readiness_v1.py`
- `tools/audit_core_v3_pressure_initializer_readiness.py`
- `tests/test_core_v3_pressure_initializer_readiness_v1.py`
