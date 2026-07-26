# DD-106 Core V3 Pressure-Consistent Initializer Contract

## Decision

DD-106 passes its property-free structural gate. One separately frozen live
numerical initializer contract may be drafted. No DWSIM property call,
initializer solve, timestep, trajectory, controller, or integration occurred.

## Why This Is Different

DD-105 showed that the DD-094 state cannot enter the pressure-enabled model by
using the first backward-Euler step as an initializer. The `1.0 s` and `0.5 s`
roots were individually exact but materially different, so the first timestep
was deciding how much inventory and energy moved.

DD-106 removes time from initialization. It defines one equality-constrained
problem over:

| Primal block | Count |
|---|---:|
| Positive component inventories `N[j,k]` | 15 |
| Continuous inventory rates `dN[j,k]/dt` | 15 |
| Pressure-enabled algebraic variables | 27 |
| **Total** | **57** |

The following remain exact constraints, never weighted penalty residuals:

| Constraint block | Count |
|---|---:|
| Existing pressure-enabled DAE rows | 42 |
| Whole-column component totals | 3 |
| Whole-column stored energy | 1 |
| Drum and sump total molar inventories | 2 |
| **Total** | **48** |

The terminal constraints preserve total holdup, corresponding to level
ownership, while allowing terminal compositions to move. Locking every
terminal component would overconstrain the phase reconciliation.

## Selection Rule

The 48 independent equalities leave a nine-dimensional feasible manifold. A
normalized quadratic objective selects one point by preferring, in declared
form:

1. small component-inventory rates;
2. small conserved-state redistribution from DD-094;
3. small algebraic movement from the declared pressure seed.

The objective selects among exactly feasible states. It is not permitted to
trade material balance, energy balance, equilibrium, hydraulics, or pressure
closure against proximity to the seed.

## Structural Result

```text
primal variables                 57
exact equality constraints       48
equality structural rank         48
feasible-manifold dimension       9
KKT dimension                   105
KKT structural rank             105
KKT structural nullity            0
zero rows / primal columns       0 / 0
unregistered dependencies         0
objective-uncovered variables     0
```

All three global component constraints cover all five volumes. The stored-
energy constraint depends on all 15 inventories, all five temperatures, and
all four solved lower pressures. The 42 DD-104 DAE rows are inherited without
replacement. There is no timestep or backward-Euler dependency.

## Next Authorized Increment

One live numerical contract may now be prepared and committed before use. It
must freeze:

- the DD-094 component and stored-energy totals;
- the DD-094 drum and sump total holdups;
- positive state coordinates and physical pressure ordering;
- provider-derived live stored energy at the trial pressure;
- objective normalization and relative weights before execution;
- one constrained solver and derivative strategy;
- DAE, conservation, terminal-ownership, phase, hydraulic, pressure, rank,
  conditioning, movement, rate, provider-call, and wall-clock gates;
- a hard stop with no retry, timestep experiment, continuation, or weight
  tuning after results are known.

A live pass would produce only a candidate pressure-consistent initial state.
It must still pass an independent zero-time consistent-rate audit and then a
separately frozen refined first-step gate before any trajectory is authorized.

Primary evidence:

- `logs/dd106_core_v3_pressure_consistent_initializer_20260726.json`
- `src/dynamic_distillation/core_v3/pressure_consistent_initializer_contract_v1.py`
- `tools/audit_core_v3_pressure_consistent_initializer.py`
- `tests/test_core_v3_pressure_consistent_initializer_contract_v1.py`
