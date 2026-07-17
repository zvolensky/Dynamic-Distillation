# DD-066: Terminal Conserved Inventory Mapping

Date: 2026-07-17

## Purpose

DD-065 proved that the accepted C3/C4 checkpoint closes locally on all active
interior trays but fails the global pressure/vapor-flow network. It also
reported terminal inventory that the simultaneous sandbox did not represent.

DD-066 makes terminal ownership explicit before changing the algebraic
equations. This prevents a later solver from appearing conservative while
silently omitting condenser, drum, reboiler, or sump material.

## Topology Map

| Checkpoint block | Algebraic role | Inventory, lbmol | Fixed volume, ft3 |
|---|---|---:|---:|
| Stage 1 | Eliminated empty total-condenser placeholder | `1.32e-14` | `0` |
| Top boundary | Reflux drum | `1516.2691` | `4330.1423` |
| Stage 20 | Partial reboiler | `12.6862` | `291.9001` |
| Bottom boundary | Bottoms sump | `791.9272` | `3113.6011` |

The reflux drum includes `107.7290 lbmol` of vapor. The sump vapor inventory
is approximately `1e-8 lbmol`.

The total-condenser stage deserves special treatment. Its material inventory
is numerical zero. Subtracting `P*V` from its zero phase-enthalpy inventory as
if it were a physical empty fixed-volume vessel creates approximately
`-35,000 BTU` of meaningless internal energy. The mapper now identifies this
stage as an algebraic topology placeholder and assigns it no conserved volume
or energy.

## Conservation Result

The mapped full-column checkpoint contains:

| Component | Total, lbmol |
|---|---:|
| Propane | `1856.5410376` |
| n-Butane | `1456.3330230` |
| n-Pentane | `198.2580300` |

Accounting errors are:

- maximum component error: `2.27e-13 lbmol`;
- total internal-energy error: `1.86e-9 BTU`.

This passes the inventory-accounting portion of `FR-019g`.

## What Does Not Yet Pass

The two physical terminal assemblies were also closed independently with the
same DWSIM PR UV formulation used for the interior trays:

| Assembly | Temperature, F | Pressure, psia | Vapor fraction |
|---|---:|---:|---:|
| Total condenser plus reflux drum | `114.838` | `213.564` | `0.06358` |
| Partial reboiler plus bottoms sump | `205.237` | `199.616` | `0.08696` |

Both UV solves converge without an accepted projection, but their pressure
ordering is physically wrong:

```text
P_bottom - P_top = -13.9476 psi
```

The terminal conserved totals, energies, and volumes therefore cannot be
inserted unchanged into an upward-vapor-flow pressure network.

The current simultaneous algebraic solve still has:

- local interior `T`, `P`, and phase fraction;
- liquid-only top and bottom node temperatures;
- column liquid and vapor traffic.

It does not yet place the conserved reflux-drum, partial-reboiler, and sump
component totals, internal energies, phase splits, and volume equations in the
same residual. Therefore:

```text
terminal inventory accounting complete = true
terminal algebraic coupling complete = false
```

The DD-065 hydraulic failure is unchanged:

- liquid-flow scaled residual: `1.0545`;
- vapor/pressure-drop scaled residual: `6.8154`;
- local-versus-global pressure mismatch: `86.78 psi`;
- all 18 interior liquid and vapor limiters active.

## Decision

This is forward progress, but not a model acceptance result. Terminal
inventory can no longer disappear from the audit, and blindly enlarging the
frozen-state solver is now ruled out.

The next implementation slice must allow tray and terminal conserved
inventories and energies to redistribute while preserving whole-column
component totals and total internal energy. The solve must impose a physically
ordered pressure network and the specified operating degrees of freedom. The
frozen checkpoint remains the regularization reference, not an equality
constraint on every local conserved state.

Do not change the production RHS or begin a one-step implicit dynamic
prototype until that globally conservative redistribution probe and the
uncapped hydraulic network pass independently.

## Evidence

- `src/dynamic_distillation/frozen_checkpoint_closure_v1.py`
- `tools/audit_frozen_checkpoint_closure.py`
- `tests/test_frozen_checkpoint_closure_v1.py`
- `logs/frozen_checkpoint_closure_terminalmap_20260717.json`
- `logs/frozen_checkpoint_closure_terminalmap_20260717.md`
