# DD-108 Core V3 Conserved N/U Pressure-DAE Contract

## Decision

DD-108 passes the property-free structural gate. One separately frozen live
numerical rank and constraint-manifold contract may be drafted. No property
call, state solve, initializer, timestep, trajectory, controller, or
integration occurred.

## Ownership Result

Energy ownership follows pressure ownership:

- The reflux-drum pressure is fixed. Bubble equilibrium therefore determines
  drum temperature from drum inventory, and top internal energy remains a
  derived storage function with its exact fixed-pressure saturation gradient.
- The four lower pressures are algebraic unknowns. Each corresponding volume
  receives an independent conserved `U[j]` state, an exact `dU[j]/dt` rate,
  and one live liquid-storage constitutive equation.

For each lower volume:

```text
U[j] = NL[j] * (hL(T[j],P[j],x[j])
                - P[j] / rhoL(T[j],P[j],x[j]))
```

Liquid enthalpy and density remain provider-owned. Component inventories
determine `NL` and `x`. There is no reduced moving-pressure gradient and no
initializer timestep.

## Why Top U Is Not Independent

The first structural assembly gave all five volumes independent `U/dU`
ownership. It was square at `47 x 47` but had structural rank `46`; the
unmatched row was top liquid-energy storage and the unmatched variable was
`Q_C`.

That is not a numerical accident. Fixed top pressure plus three bubble-
fugacity equations already determine drum temperature and incipient vapor
composition. Adding an independent top storage equation duplicates one
constraint on those same algebraic coordinates.

Retaining derived top energy and independent lower energy removes the
duplication without an artificial anchor. The corrected ledger is:

| Block | Count |
|---|---:|
| Component-inventory states `N[j,k]` | 15 |
| Independent lower internal-energy states `U[j]` | 4 |
| Component-inventory rates | 15 |
| Lower internal-energy rates | 4 |
| Algebraic variables, including four lower pressures | 27 |
| Physical and storage equations | 46 |

## Structural Result

```text
state coordinates                 19
derivative variables              19
algebraic variables               27
solve variables / equations    46 / 46
structural rank / nullity       46 / 0
storage closures                   4
pressure-drop rows                 4
pressure-rate variables            0
zero rows / columns              0 / 0
```

The result also passes for a generic two-component case at `36 x 36`, rank
`36`. There are no hardcoded interior positions, controller rows, profile
dependencies, caps, relaxation, previous-step inputs, explicit vapor
inventory, or second vapor-flow owner. Component and energy balance ownership
remain conservative.

## Next Authorized Increment

One live numerical contract may be prepared and committed before execution.
It must freeze:

- the exact DD-094 `N` state and four provider-derived lower `U` values;
- the DD-103 pressure state as a guess only;
- direct liquid enthalpy/density and all existing provider ownership;
- full `46 x 46` leading-Jacobian steps, scales, rank, condition, spectrum,
  and registered-coupling gates;
- the separate state-constraint Jacobian for four lower storage equations and
  all saturation/pressure algebraic constraints;
- exact zero-rate recovery only if the state is actually consistent;
- property-call and wall-clock ceilings, with colored derivatives considered
  before execution;
- a hard stop without solver tuning, hidden timestepping, projection,
  continuation, or alternate energy ownership.

A numerical structural pass would authorize a separately frozen
conservation-constrained initializer formulation. It would not itself
authorize an initializer solve or dynamics.

Primary evidence:

- `logs/dd108_core_v3_conserved_nu_pressure_dae_20260726.json`
- `src/dynamic_distillation/core_v3/conserved_nu_pressure_dae_contract_v1.py`
- `tools/audit_core_v3_conserved_nu_pressure_dae.py`
- `tests/test_core_v3_conserved_nu_pressure_dae_contract_v1.py`
