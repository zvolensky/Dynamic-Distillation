# DD-077: Core V2 Reduced Structural Registry

Date: 2026-07-18

## Purpose

DD-077 is the first implementation increment under the DD-076 equilibrium-DAE
architecture contract. It is not another DD-075 solver or release-order
variation.

This increment answers only structural questions:

- what are the five inventory-bearing control volumes;
- which quantities are differential states, algebraic unknowns, or parameters;
- which equation owns every unknown;
- whether the steady root registry is square and structurally full rank;
- whether internal component and energy stream terms telescope;
- whether pressure, liquid flow, and vapor flow have one owner.

It contains no property evaluation, nonlinear solve, or dynamic integration.

## First-Layer Vapor Decision

The reduced feasibility model uses two prescribed section rates:

```text
V_rectifying
V_stripping
```

They are parameters, not algebraic unknowns and not imported profile values.
This deliberately postpones condenser/reboiler energy-to-vapor coupling until
the reduced thermodynamic, energy, and Francis system has a verified physical
root.

An energy-determined vapor-flow layer requires a separate gate. It may not be
introduced as a silent reinterpretation of these parameters.

## Topology

Inventory-bearing volumes:

1. reflux drum;
2. rectifying tray;
3. feed tray;
4. stripping tray;
5. combined partial reboiler and bottoms sump.

The total condenser has no inventory node. The overhead vapor stream enters
the reflux drum as a fully condensing internal stream.

The three tray liquid outlets are algebraic unknowns owned only by their
Francis equations. Reflux is a specified terminal transfer. Pressure is
prescribed data at every volume.

## Structural Form

For the three-component C3/C4 audit, the steady registry contains:

| Block | Unknowns | Residuals |
|---|---:|---:|
| Component inventory / reconstruction | 15 | 15 |
| Internal energy / reconstruction | 5 | 5 |
| Liquid amount | 5 | - |
| Liquid composition | 10 | - |
| Temperature | 5 | - |
| Vapor composition / equilibrium | 8 | 8 |
| Component balances | - | 15 |
| Energy balances | - | 5 |
| Francis liquid flow / hydraulics | 3 | 3 |
| Terminal product flow / level specifications | 2 | 2 |
| **Total** | **53** | **53** |

Liquid amount, composition, and temperature are closed through reconstruction,
balance, hydraulic, and terminal-level rows rather than through one residual
block with the same label.

## Initial Structural Stop

The first registry fixed both product rates and contained no terminal inventory
specifications. It was square but structurally deficient:

```text
unknowns/residuals = 51 / 51
structural rank    = 49
structural nullity = 2
```

The unmatched unknowns were:

```text
NL[reflux_drum]
NL[combined_reboiler_sump]
```

This was a physical ownership failure. At steady state, fixed terminal product
rates do not determine the two terminal liquid inventories.

## Ownership Correction

The corrected steady specification:

- specifies reflux-drum liquid amount;
- specifies combined-bottom liquid amount;
- promotes distillate flow `D` to an algebraic unknown;
- promotes bottoms flow `B` to an algebraic unknown.

The product rates are therefore the flows required to satisfy steady terminal
inventory balances at the specified levels. This is a steady operating
specification, not a controller equation.

No tolerance, rank method, solver option, tray count, or property behavior was
changed.

## Corrected Gate Result

The corrected registry reports:

```text
unknowns/residuals = 53 / 53
structural rank    = 53
structural nullity = 0
```

Additional gates pass:

- no empty or unmatched rows or columns;
- no duplicate unknown or residual names;
- every unknown names an existing closure residual;
- prescribed pressure is used only as parameter data;
- both section vapor rates are used only as parameter data;
- every tray liquid-flow unknown has one Francis owner;
- no imported profile or ChemSep value enters a residual dependency;
- every internal component stream contribution cancels exactly;
- every internal energy stream contribution cancels exactly;
- `core_v2` imports no governing equation from the legacy runtime.

Evidence:

- `logs/dd077_core_v2_structural_audit_20260718.json`
- `logs/dd077_core_v2_structural_audit_20260718.md`
- `tests/test_core_v2_reduced_registry_v1.py`

## Decision

DD-077 passes the structural gate.

The next authorized increment is a property-free Gate A source-equation
residual evaluator and comparison against the accepted Skogestad equation
assembly. It may evaluate residuals, but it may not add live DWSIM calls,
nonlinear solves, or dynamic integration.
