# DD-070: Canonical Checkpoint Repair Decision

Date: 2026-07-17

## Purpose

DD-069 found that DD-068 used non-neutral movement scaling, treated an
unowned sump headspace as part of the conserved UV volume, and conserved
serialized phase enthalpy that did not match live DWSIM properties. DD-070
performs the one corrected checkpoint-repair attempt authorized by the
external review.

The attempt is deliberately bounded. It uses the same five starts and fixed
acceptance criteria. No optimizer retuning is permitted after the result.

## Corrected Basis

- Every node uses live DWSIM phase enthalpy and occupied phase volume to
  construct canonical internal energy.
- All nodes use one common whole-column energy movement scale.
- Each component uses one common whole-column inventory scale.
- The reflux drum owns its resident vapor.
- The reboiler stage owns reboiler vapor.
- The bottoms sump is liquid-only; unoccupied headspace is excluded from the
  sump UV target.
- Whole-column component and canonical internal-energy totals are conserved by
  the redistribution solve.

Canonicalization changed whole-column internal energy from
`-16,038,840.9 BTU` to `-17,246,038.2 BTU`, a `-1,207,197.3 BTU` replacement.
The per-mole enthalpy differences varied materially across the column
(`1.738` relative spread), so the mismatch is state-dependent rather than a
single removable reference offset.

## Five-Start Result

| Start | Converged | Objective | Energy moved, BTU | Material moved, lbmol | Maximum pressure correction, psi |
|---|---:|---:|---:|---:|---:|
| Checkpoint | No | `5.27355e-5` | `134,207` | `16.119` | `25.337` |
| DD-067 | No | `5.27543e-5` | `134,176` | `16.123` | `25.334` |
| Linear pressure | Yes | `6.38279e-5` | `159,739` | `13.640` | `23.335` |
| Small random | No | `5.27636e-5` | `133,994` | `16.198` | `25.334` |
| Moderate random | No | `5.27652e-5` | `134,102` | `16.142` | `25.339` |

Canonicalization materially improved the apparent movement problem:

- energy movement fell below DD-067's `747,127 BTU`;
- maximum pressure correction fell below DD-068's `79.159 psi`;
- equal physical energy moves have equal objective cost;
- terminal movement is not excessive relative to terminal energy capacity;
- the converged linear candidate passes conservation, local UV closure,
  volume, and bound checks.

Those improvements do not overcome the robustness failure. Only one of five
starts converged. The four rejected starts retained pressure-order violations
from `0.00151` to `0.03811 psi`, and no repeatable accepted movement pattern
exists.

## Gate Decision

Classification: `dd070_checkpoint_repair_retired`.

Failed predefined criteria:

1. at least four of five starts converge;
2. objective basin is reproduced;
3. movement pattern is reproduced;
4. checkpoint enthalpy reconciliation is not state-dependent.

Checkpoint repair is retired. Do not retune this optimizer, run another
checkpoint-repair variant, or add hydraulics to the DD-070 candidate.

## Next Architecture Step

Formulate the steady state directly from operating specifications using
conserved component inventories and total internal energy as state variables.
The direct nonlinear system must solve local UV equilibrium together with
pressure, vapor flow, liquid flow, energy, feed, product, condenser, reboiler,
and terminal-equipment equations. Imported profiles and the operational
checkpoint may supply initial guesses and comparison targets, but their
serialized phase split and enthalpy are not conserved truth.

Only after the direct system passes local, global hydraulic, terminal,
controller-DOF, multi-start, and safeguard gates should it be serialized and
tested dynamically.

## Evidence

- `logs/canonical_checkpoint_repair_20260717.json`
- `logs/canonical_checkpoint_repair_20260717.md`
- `src/dynamic_distillation/canonical_checkpoint_repair_v1.py`
- `src/dynamic_distillation/least_movement_redistribution_v1.py`
- `tools/solve_canonical_checkpoint_repair.py`
- `tests/test_canonical_checkpoint_repair_v1.py`
- `tests/test_least_movement_redistribution_v1.py`
