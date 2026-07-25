# DD-095 Core V3 Dynamic DAE Structural Contract

Date: 2026-07-25

## Decision

DD-095 passes its structural gate. The reduced Core V3 dynamic extension has
a square `38 x 38` implicit derivative/algebraic ledger with structural rank
`38` and nullity zero.

This is a contract and dependency audit only. No numerical mass matrix,
DWSIM property derivative, nonlinear solve, controller, initializer, or
dynamic integration was attempted.

## DD-094 Qualification

DD-094 remains an accepted reduced-model feasibility root. It is not a
production design-point result.

At the fixed `218.44 psia` drum pressure, the accepted reduced root has:

```text
T_D = 133.713293 F
x_D = [0.703001, 0.283606, 0.013393]
```

The frozen source reference has:

```text
T_D = 117.816385 F
x_D = [0.905668, 0.094326, 0.000006]
```

The `15.896909 F` temperature difference follows the much heavier drum
composition. It does not invalidate the DWSIM bubble calculation, but it
prevents using DD-094 as a production-quality or full-column initialization
acceptance result. Production scaling must add separate terminal temperature,
composition, and product-rate gates.

## Why Internal Energy Is Derived

Core V3 prescribes pressure, neglects resident vapor holdup, and enforces all
component fugacity equalities. Those equations put each equilibrium volume on
a saturated liquid/vapor manifold. At fixed pressure and liquid composition,
they determine temperature and equilibrium vapor composition.

An additional independent `U[j]` coordinate would therefore duplicate a
thermodynamic constraint. It would require either:

- an index-2 constraint treatment with vapor flows and duty acting as
  multipliers;
- explicit vapor inventory and volume closure; or
- released pressure ownership.

None is authorized in this reduced layer. DD-095 instead uses the provider
consistent storage function:

```text
U[j] = NL[j] * uL(T[j], P[j], x[j])
```

and places its chain-rule derivative in the energy balance:

```text
dU[j]/dt = sum_k (partial U[j]/partial N[j,k]) * dN[j,k]/dt
```

Energy remains exactly conserved. It is not an independently integrable
coordinate under the current physical assumptions.

## Coordinates And Unknowns

The independent state coordinates are the `15` component inventories:

```text
N[j,k],  j = 1..5, k = 1..3
```

At a fixed state, one implicit evaluation solves for:

| Block | Count |
|---|---:|
| Component-inventory derivatives | 15 |
| Temperatures | 5 |
| Independent stage-vapor compositions | 8 |
| Francis liquid flows | 3 |
| Energy-owned vapor links | 4 |
| Condenser incipient-vapor coordinates | 2 |
| Energy-owned condenser duty | 1 |
| **Total** | **38** |

## Equations

| Block | Count |
|---|---:|
| Component balances | 15 |
| Energy balances with derived-storage derivative | 5 |
| Full stage-fugacity equilibrium | 12 |
| Francis hydraulics | 3 |
| Condenser bubble fugacity | 3 |
| **Total** | **38** |

For `C` components, both counts are `10*C + 8`.

The exact structural incidence uses only adjacent liquid and vapor links.
There are no empty rows, empty solve-variable columns, unregistered
dependencies, terminal-amount constraints, controller rows, or profile
dependencies.

## Open-Loop Ownership

The first reduced dynamic audit freezes at the DD-094 operating point:

- prescribed ordered pressure profile;
- fixed feed rate, composition, temperature, pressure, and enthalpy;
- fixed reflux `R` and reboiler duty `Q_R`;
- fixed `D=2085.666033 lbmol/h`;
- fixed `B=5057.307967 lbmol/h`;
- fixed hydraulic geometry.

The four vapor links and `Q_C` remain simultaneous energy-owned algebraic
quantities. The three internal liquid links remain Francis-owned. No level,
pressure, temperature, composition, or duty controller is present.

Freezing `D/B` removes the steady solver's two terminal-amount constraints
and allows drum and sump inventories to respond dynamically. Controllers may
be introduced only after the natural open-loop model passes.

## Index Status

The property-free dependency matrix is a full-rank, implicit-index-1
candidate. DD-095 does not claim a numerical DAE index.

Before any integration, DD-096 must evaluate the live leading Jacobian:

```text
partial F / partial (dN/dt, algebraic variables)
```

at the exact DD-094 root using the frozen finite-difference steps `1e-5` and
`5e-6`. Both must retain rank `38/38`, stable singular spectra, declared
provider ownership, exact conservation, and no off-registry coupling.

## Consistent Initialization

The sole initial state for the first numerical audit is obtained exactly by:

```text
N[j,k] = NL_DD094[j] * x_DD094[j,k]
```

The DD-094 temperatures, vapor compositions, liquid/vapor flows, bubble
composition, and condenser duty supply the algebraic initial guess. A
consistent endpoint must recover:

```text
dN[j,k]/dt = 0
max|scaled F| < 1e-8
leading Jacobian rank = 38
```

No projection, repair, relaxation, profile forcing, or alternate root may be
used.

## Structural Result

```text
state coordinates       = 15
derivative variables    = 15
algebraic variables     = 23
rows                    = 38
structural rank         = 38
structural nullity      = 0
zero rows/columns       = 0 / 0
```

Eight DD-095 tests and all `35` focused Core V3 tests pass.

## Hard Stops

Stop before integration if DD-096 finds:

- leading-Jacobian rank below `38` at either step;
- a nonzero derivative at the DD-094 root above the declared tolerance;
- inconsistent property bases between stored energy and stream enthalpy;
- component or energy telescoping failure;
- an off-registry dependency or second flow owner;
- a need for controller action, clipping, fallback, relaxation, or profile
  forcing.

Do not respond to a failure with integrator tuning or a different initial
state.

## Authorization

DD-095 authorizes drafting and precommitting one DD-096 live
leading-Jacobian, provider-chain-rule, conservation, and
consistent-derivative audit.

DD-095 does not authorize numerical mass-matrix implementation, dynamic
integration, perturbation runs, controllers, production tray count, pressure
dynamics, or vapor holdup.

Primary evidence:

- `src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py`
- `tools/audit_core_v3_dynamic_dae_contract.py`
- `tests/test_core_v3_dynamic_dae_contract_v1.py`
- `logs/dd095_core_v3_dynamic_dae_contract_20260725.json`
- `logs/dd095_core_v3_dynamic_dae_contract_20260725.md`
