# DD-071: Direct Conserved Steady-State Registry

Date: 2026-07-18

## Purpose

DD-070 retired checkpoint repair and directed the initializer architecture
toward a direct conserved steady-state formulation. DD-071 begins that work
with a deterministic unknown/residual registry and structural-rank audit. It
does not evaluate a nonlinear residual or attempt a steady-state solve.

## Reduced Composition Basis

The registry uses the first `Nc-1` liquid and vapor mole fractions as
independent unknowns and reconstructs the final fraction by normalization.
This removes explicit composition-normalization rows and their expected
redundancy.

Every two-phase conserved node owns:

- total component inventories;
- total internal energy;
- temperature and pressure;
- liquid and vapor phase amounts;
- independent liquid and vapor compositions.

Local component, energy, volume, and equilibrium equations are explicit.
Steady component and energy balances are separate residual blocks.

## Separate Reboiler And Sump Proposal

The external-review proposal initially represented the partial reboiler and
liquid-only sump as separate conserved nodes.

| Quantity | Result |
|---|---:|
| Unknowns | `291` |
| Residuals | `290` |
| Structural rank | `290` |
| Structural nullity | `1` |
| Empty rows or columns | `0` |

The missing owner is:

```text
L_out[partial_reboiler_to_bottoms_sump]
```

Separate reboiler and sump inventories require a physical equation for that
liquid transfer: valve law, overflow/weir relation, level controller,
circulation specification, or equivalent. None exists in the accepted four
control pairs. Adding an arbitrary residence-time or tuning equation merely
to make the system square is prohibited.

## Selected Bottom Topology

DD-071 therefore retains the DD-070 ownership decision and combines reboiler
vapor plus sump liquid inside one conserved bottom control volume. The
internal reboiler-to-sump transfer crosses no boundary of that control volume
and is eliminated algebraically. The reboiler and sump remain explicit phase
owners; their conserved material and energy are not discarded.

| Quantity | Result |
|---|---:|
| Unknowns | `281` |
| Residuals | `281` |
| Structural rank | `281` |
| Structural nullity | `0` |
| Empty rows | `0` |
| Unused unknown columns | `0` |
| Missing closure owners | `0` |

Unknown blocks include `60` component inventories, `20` internal energies,
`40` local thermo variables, `40` phase amounts, `80` independent phase
compositions, `18` liquid flows, `19` vapor flows, and four manipulated
variables.

The four steady control pairs remain:

| Specification | Unknown |
|---|---|
| Reflux-drum liquid level | Distillate flow |
| Bottom liquid level | Bottoms flow |
| Top pressure | Condenser duty |
| Bottoms propane mole fraction | Reboiler duty |

## Decision

Classification: `dd071_registry_structure_passed_combined_bottom`.

The equation-count, ownership, empty-row/column, and structural-rank gates
pass for the combined bottom control volume. This authorizes the next DD-071
slice: numerical residual evaluation using live DWSIM properties at the
ChemSep, checkpoint, and perturbed guesses.

It does not authorize a nonlinear solve. Numerical residual finiteness,
scaling, telescoping conservation, and numerical Jacobian rank remain
unverified.

## Evidence

- `src/dynamic_distillation/direct_steady_state_registry_v1.py`
- `tools/audit_direct_steady_state_registry.py`
- `tests/test_direct_steady_state_registry_v1.py`
- `logs/direct_steady_state_registry_20260718.json`
- `logs/direct_steady_state_registry_20260718.md`
