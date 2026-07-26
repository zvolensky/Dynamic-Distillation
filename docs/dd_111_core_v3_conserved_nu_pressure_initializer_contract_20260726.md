# DD-111 Conserved N/U Pressure Initializer Contract

- Classification: `dd111_structural_passed`
- Decision: `authorize_one_frozen_live_constrained_initializer_contract`
- Primal variables: `65`
- Exact constraints/rank: `52/52`
- Feasible-manifold dimension: `13`
- KKT dimension/rank: `117/117`
- Live property calls: `False`
- Initializer solve or timestep: `False`

The four lower internal-energy states and rates correct DD-106's missing continuous pressure-aware energy ownership. One separately frozen live constrained-initializer contract may be drafted; execution remains unauthorized.

## Ownership

| Primal block | Count |
|---|---:|
| Positive component inventories `N[j,k]` | 15 |
| Lower internal energies `U[j]` | 4 |
| Component rates `dN[j,k]/dt` | 15 |
| Lower energy rates `dU[j]/dt` | 4 |
| Algebraic variables, including four lower pressures | 27 |
| **Total** | **65** |

The reflux drum does not receive an independent `U` state. Its energy rate
remains the exact reduced derivative on the fixed-pressure saturation
manifold. The four lower pressure-owning volumes have independent `U/dU`
pairs and live storage closures.

## Exact Constraints

| Constraint block | Count |
|---|---:|
| Conserved-`N/U` pressure DAE rows | 46 |
| Whole-column component totals | 3 |
| Whole-column stored energy | 1 |
| Drum and sump total inventories | 2 |
| **Total** | **52** |

Whole-column energy is the derived top storage plus the four independent
lower energy states. The four DAE storage rows separately require each lower
energy state to equal the live pressure-dependent thermo storage. Terminal
constraints preserve total holdup while allowing composition to reconcile.

## Selection Rule

A positive normalized quadratic objective covers every primal variable and
prefers small conserved rates, small conserved-state movement, and small
algebraic movement. It selects among exactly feasible states; it may not trade
conservation, storage, equilibrium, hydraulics, or pressure closure against
seed proximity.

## Next Contract

Before any solve, the numerical successor must commit the exact reference
state and conservation targets, physical bounds and transformations,
objective scales and weights, one constrained solver and derivative strategy,
rank and conditioning limits, provider/call/wall limits, and a no-retry hard
stop. A pass would produce only an initializer candidate. It would still need
an independent zero-time rate audit and refined first-step gate before any
trajectory.
