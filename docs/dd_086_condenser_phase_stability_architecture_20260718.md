# DD-086 Condenser Phase-Stability Architecture

## Decision

Core V2 is not frozen at DD-085. A materially new, structural-only condenser
architecture is authorized.

DD-086 is not solver tuning and does not reopen the retired DD-085 system. It
preserves the successful four-vapor-link interior MESH core and replaces only
the physically invalid fixed-duty total-condenser boundary.

No nonlinear root solve, continuation, bound change, duty sweep, or dynamic
integration is part of DD-086.

## Direct DD-085 Phase Diagnosis

The preserved DD-085 common root reports:

```text
T_drum = 166.130673 F
P_drum = 218.44 psia
z_drum = [0.62888446, 0.35270349, 0.01841205]
```

A live DWSIM PR TP evaluation at that exact state returns:

```text
K = [1.48947446, 0.67056276, 0.35544741]
Rachford-Rice beta = 0.9999999995
phase classification = vapor
```

The phase-specific liquid enthalpy nevertheless matches:

```text
h_vapor,in + Q_C / V_top = -4700.18879851 BTU/lbmol
h_liquid(T_drum,P_drum,z) = -4700.18879851 BTU/lbmol
error                       = -4.73e-11 BTU/lbmol
```

This confirms the DD-085 mechanism. The backend can evaluate a mathematical
liquid enthalpy at a state whose stable TP phase is vapor. Energy closure is
not a phase-stability test.

The DD-085 root remains a mathematically accepted and physically rejected
diagnostic reference.

## Retired Boundary

The following combination remains retired:

- inventory-free total condenser;
- prescribed condenser duty;
- liquid-only reflux drum;
- independently solved drum temperature;
- no outlet flash, bubble constraint, or phase-stability test.

Fixed duty may still be used as an input to a PH/TP feasibility audit. It may
not simultaneously assert complete condensation. If its outlet flash has
`beta > 0`, the topology is a partial condenser and requires a vapor outlet.

## Selected Successor

DD-086 selects a saturated-liquid total condenser for the reduced steady
architecture:

- condenser and drum pressure remain prescribed;
- the complete overhead vapor stream transfers to liquid;
- reflux and distillate retain the live drum liquid composition;
- condenser duty `Q_C` becomes an algebraic unknown;
- drum temperature and an incipient vapor composition satisfy the full
  bubble-point fugacity equations;
- the condenser energy balance determines `Q_C`;
- the accepted outlet has limiting vapor fraction `beta=0`.

Specified subcooling is not part of this increment. Adding nonzero subcooling
would require a declared subcooling parameter and another explicit ownership
audit.

## Governing Boundary Equations

The steady drum component balances remain:

```text
0 = V_top * y_top[k] - (R + D) * x_D[k]
```

The condenser/drum energy balance remains:

```text
0 = V_top * hV_top + Q_C - (R + D) * hL_D
```

but `Q_C` is now an unknown rather than a fixed parameter.

At the saturated-liquid outlet, introduce `C-1` independent incipient-vapor
coordinates `y_bubble` and enforce all `C` fugacity equalities:

```text
fL_k(T_D, P_D, x_D) = fV_k(T_D, P_D, y_bubble)
```

Normalization is intrinsic to the composition coordinates. The `C` equations
contain `C-1` relative-composition conditions plus one saturation condition.

## Degree-of-Freedom Ledger

DD-083/DD-085 contained `9*C + 10` unknowns and residuals.

DD-086 adds:

| Added block | Unknowns | Residuals |
|---|---:|---:|
| Solved condenser duty `Q_C` | 1 | 0 |
| Incipient vapor coordinates | `C-1` | 0 |
| Full condenser bubble fugacity | 0 | `C` |
| **Added total** | **`C`** | **`C`** |

The new invariant is:

```text
unknowns = residuals = 10*C + 10
```

For the three-component reduced column:

```text
unknowns/residuals = 40 / 40
structural rank    = 40
structural nullity = 0
```

`Q_C` has exactly one unknown owner and appears in the reflux-drum energy
balance. It is no longer an external parameter.

## Preserved Interior Core

DD-086 does not alter:

- four independent energy-owned vapor links;
- full fugacity equilibrium at the four equilibrium outlets;
- five component and energy control-volume balances;
- Francis-only liquid hydraulics;
- prescribed ordered pressure;
- prescribed reflux, feed, and reboiler duty;
- solved `D/B` and specified terminal liquid amounts;
- exact component and energy telescoping.

No profile, ChemSep result, previous-step flow, cap, relaxation, controller,
clipping, projection, or property fallback is introduced.

## Structural Gate

The three-component registry must have:

- `40` unknowns and `40` residuals;
- structural rank `40`;
- no zero row or column;
- no unregistered or imported-profile dependency;
- one `Q_C` unknown and no fixed `Q_C` parameter;
- two incipient-vapor coordinates and three bubble-fugacity equations;
- preserved symbolic component and energy conservation.

Passing this gate authorizes only one separately frozen live-property
numerical residual/Jacobian audit. It does not authorize a nonlinear solve.

## Next Numerical Audit

Any DD-087 numerical audit must be precommitted and must:

1. construct a saturated-liquid drum seed from live DWSIM bubble properties;
2. compute the corresponding `Q_C` from the condenser energy balance;
3. evaluate the unchanged `40 x 40` residual at the canonical state and one
   deterministic perturbation;
4. audit rank at `h=1e-5` and `h/2=5e-6`;
5. require condition below `1e8`, exact conservation, finite properties, and
   no unregistered coupling;
6. perform no nonlinear solve or integration.

The DD-085 hot-drum root may be reported diagnostically but may not be reused
as a liquid-phase canonical state.

## Stop Rule

Freeze Core V2 at DD-085 if the `40 x 40` registry is singular or if a later
live numerical audit cannot evaluate a saturated-liquid boundary with full
rank and no fallback.

Do not respond with fixed-duty retuning, removal of phase stability, partial
condenser behavior without a vapor outlet, or another solver campaign.
