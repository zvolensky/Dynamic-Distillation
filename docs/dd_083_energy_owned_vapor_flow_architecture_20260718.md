# DD-083 Energy-Owned Vapor-Flow Architecture and DOF Contract

## Decision

DD-082 permanently retires the prescribed-vapor Gate C operating
specification. It does not retire Core V2's validated material equations,
local property kernel, Francis hydraulics, or five-volume conservation
assembly.

DD-083 defines the only authorized successor architecture: a structural-only
steady MESH formulation with prescribed pressure and four independent,
energy-owned vapor links. DD-083 contains no live property evaluation,
nonlinear solve, continuation, bound experiment, or dynamic integration.

## Why DD-082 Could Not Be Retuned

All three frozen DD-082 starts reached the same full-rank endpoint, but the
scaled residual stopped at `9.15999e-3`. The reflux-drum n-pentane inventory
hit its upper bound while its component balance still missed by
`76.3345 lbmol/h`.

The failure was not caused by rank loss, conditioning, properties, initial
guess, or solver termination. It arose under an operating architecture that
prescribed the two section vapor rates. Widening bounds or changing solvers
would violate the declared hard stop.

## Physical Ownership

The DD-083 reduced model retains:

- one liquid reflux drum;
- one rectifying tray;
- one feed tray;
- one stripping tray;
- one combined partial-reboiler/sump volume;
- an inventory-free total condenser;
- prescribed ordered pressure;
- prescribed reflux and condenser/reboiler duties;
- fixed feed rate, composition, and enthalpy;
- specified terminal liquid amounts with `D` and `B` solved;
- Francis-only tray liquid outflow.

It replaces the two prescribed section vapor parameters with four independent
algebraic vapor-link unknowns:

```text
V[combined_reboiler_sump->stripping_tray]
V[stripping_tray->feed_tray]
V[feed_tray->rectifying_tray]
V[rectifying_tray->reflux_drum]
```

These flows participate directly in the simultaneous component and energy
balances. They have no profile, previous-step, relaxation, cap, or controller
owner.

## Equilibrium Correction

DD-080 and DD-081 reconstructed a vapor composition at a specified
`N/U/P` state with `C-1` relative-fugacity equations. That is a valid local
composition reconstruction for an arbitrary conserved-energy state, but it
does not assert that the liquid lies exactly on a saturated equilibrium-stage
manifold.

The DD-083 steady MESH formulation instead enforces all `C` component
fugacity equalities at each of the four equilibrium vapor outlets. In
independent-composition coordinates, this is equivalent to:

- `C-1` relative-fugacity equations; plus
- one saturation/common-fugacity condition.

The four added saturation conditions are exactly the four equations required
when the four vapor links are released.

## Three-Component DOF Ledger

The steady formulation reconstructs conserved quantities after a root rather
than treating `N` and `U` as independent steady coordinates:

```text
N[j,k] = NL[j] * x[j,k]
U[j]   = NL[j] * uL(T[j], P[j], x[j])
```

| Unknown block | Count |
|---|---:|
| Liquid amounts `NL` | 5 |
| Independent liquid compositions | 10 |
| Temperatures | 5 |
| Independent vapor compositions | 8 |
| Francis liquid flows | 3 |
| Independent vapor-link flows | 4 |
| Terminal products `D/B` | 2 |
| **Total** | **37** |

| Residual block | Count |
|---|---:|
| Component balances | 15 |
| Full component fugacity equalities | 12 |
| Energy balances | 5 |
| Francis hydraulics | 3 |
| Terminal liquid-amount specifications | 2 |
| **Total** | **37** |

For `C` components, both counts are `9*C + 10`.

## Structural Result

The generated three-component registry reports:

```text
unknowns/residuals = 37 / 37
structural rank    = 37
structural nullity = 0
vapor unknowns     = 4
full fugacity rows = 12
```

It also confirms:

- exact symbolic component and energy telescoping for every internal link;
- no unregistered dependency;
- no imported profile or ChemSep dependency;
- one Francis owner for every tray liquid flow;
- pressure, reflux, duties, feed, geometry, and terminal levels are
  parameters rather than duplicate unknowns.

Evidence:

- `src/dynamic_distillation/core_v2/energy_owned_vapor_registry_v1.py`
- `tools/audit_core_v2_energy_owned_vapor_registry.py`
- `tests/test_core_v2_energy_owned_vapor_registry_v1.py`
- `logs/dd083_energy_owned_vapor_structural_20260718.json`
- `logs/dd083_energy_owned_vapor_structural_20260718.md`

## Limits and Authorization

Structural rank does not prove that a physical root exists or that a dynamic
DAE is well posed. DD-083 authorizes only an independently frozen numerical
residual audit with live DWSIM properties.

Before any solve, that audit must verify:

- all 37 residuals on the declared property basis;
- full numerical rank at two finite-difference steps;
- exact component and energy telescoping;
- physical temperatures, compositions, levels, and positive flows;
- no clipping, projection, property fallback, profile forcing, or limiter;
- no reuse of DD-082 bounds or solver campaign.

Dynamic conserved `N/U` integration remains unauthorized. A later dynamic
contract must derive the mass-matrix/index structure explicitly; it may not
silently reuse the DD-080 relative-fugacity reconstruction as the complete
equilibrium-stage constraint.

## Stop Rule

Stop this architecture if the structural ledger loses rank when translated
to the live residual, if the full fugacity conditions cannot be evaluated
without fallback, or if the fixed numerical audit exceeds the declared
conditioning limit. Do not respond with solver tuning, a tray-count ladder,
or another operating-specification variant.
