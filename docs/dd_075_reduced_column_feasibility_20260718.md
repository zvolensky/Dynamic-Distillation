# DD-075: Reduced-Column Conserved-Equation Feasibility

Date: 2026-07-18

## Purpose

DD-075 is the final bounded feasibility test authorized after manual staged
continuation was retired. It asks whether the same direct conserved equations
can reach a physical steady root on a five-volume column before the project
invests in full-system pseudo-transient or derivative infrastructure.

This is one reduced topology and one fixed solver recipe. It is not a
tray-count continuation ladder.

## Frozen Baseline And Branch

The full-column continuation work is frozen at commit `5bf3439` on
`refactor/compute-efficiency`. DD-075 was developed separately on
`diagnostic/reduced-column-feasibility`.

## Reduced Topology

The reducer samples source stages by physical role rather than case-specific
tray numbers:

1. reflux drum/top boundary;
2. one rectifying tray midway between the top and feed;
3. the source feed tray;
4. one stripping tray midway between the feed and bottom;
5. combined reboiler/sump bottom volume.

For the C3/C4 source profile this deterministic rule selected source stages
`1, 6, 12, 16, 20` and mapped the feed to reduced stage `3`.

The reduced case retains:

- live DWSIM Peng-Robinson properties;
- conserved component totals and internal energy;
- local component, energy, volume, and equilibrium equations;
- Francis liquid hydraulics from sampled geometry;
- vapor pressure-drop equations;
- live feed and product compositions;
- top pressure, bottoms light-key, and terminal level specifications;
- combined reboiler/sump ownership established by DD-071.

No residual family is removed. Imported flows initialize the guess but do not
replace a residual.

## Structural And Numerical Gates

For three components the reduced registry contains:

- `71` unknowns;
- `71` residuals;
- structural rank `71`;
- structural nullity `0`;
- no empty residual rows or unused unknown columns;
- no unmatched unknown or residual.

The initial live DWSIM Jacobians are also full rank at both predefined seeds
and at finite-difference steps `h` and `h/2`:

| Seed/audit | Rank | Condition estimate |
|---|---:|---:|
| ChemSep `h` | `71/71` | `2.476e7` |
| ChemSep `h/2` | `71/71` | `2.451e7` |
| Perturbed `h` | `71/71` | `2.922e7` |
| Perturbed `h/2` | `71/71` | `2.752e7` |

The numerical authorization gate therefore passed and both solver methods
were run. Component and energy telescoping passed at every evaluated endpoint.

## Fixed Solver Results

| Method | Seed | Solver termination | Scaled infinity residual | Final rank | Condition |
|---|---|---|---:|---:|---:|
| Trust region | ChemSep | `xtol` | `0.034976` | `71/71` | `4.571e11` |
| Trust region | Perturbed | `xtol` | `0.035503` | `70/71` | `1.688e14` |
| Pseudo-transient | ChemSep | minimum pseudo-time | `0.464495` | `71/71` | `1.740e7` |
| Pseudo-transient | Perturbed | minimum pseudo-time | `0.465520` | `71/71` | `1.742e7` |

All final states retained positive flows, ordered positive pressures, exact
global conservation, no accepted clipping or projection, no property
fallback, and no coordinate saturation. None reached the required physical
residual below `1e-7`.

The trust-region endpoints are dominated by steady component balances
(`0.0350` to `0.0355`) and operating specifications (about `0.0137`).
The pseudo-transient endpoints stop earlier with liquid hydraulics
(`0.464` to `0.466`), steady component balances (`0.410` to `0.412`), and
vapor pressure drop (`0.323` to `0.333`) still open.

## Interpretation

DD-075 does not prove mathematically that no physical root exists. It does
show that:

- the reduced system is neither structurally singular nor initially
  numerically rank deficient;
- the failure persists under two materially different solver architectures;
- two predefined physical seeds do not produce an accepted root;
- the residual floor cannot be attributed to clipping, property fallback,
  pressure reversal, negative flow, or conservation loss;
- the agreed bounded feasibility test has failed.

Under the predefined hard stop, another reduced topology, tray-count ladder,
equation-block removal, tolerance change, solver-option sweep, or
pseudo-time tuning campaign is not authorized.

## Decision

Classification: `reduced_feasibility_solve_gate_failed`.

Retire the present direct conserved steady-state formulation as the production
initializer architecture. Do not begin a `281`-variable pseudo-transient
program on this formulation.

This decision does not discard the accepted DD-058 operational checkpoint or
the validated source-topology model. It separates those useful artifacts from
the failed attempt to establish a rigorous full-topology conserved
steady-state initializer.

Any future rigorous architecture should restart from a simpler independently
validated equilibrium-stage foundation with a known steady solution and
introduce conserved energy, volume ownership, pressure drop, and terminal
equipment in separately proven increments. That is a redesign, not DD-076
solver tuning.

## Evidence

- `src/dynamic_distillation/reduced_column_feasibility_v1.py`
- `tools/evaluate_reduced_column_feasibility.py`
- `tests/test_reduced_column_feasibility_v1.py`
- `logs/reduced_column_feasibility_20260718.json`
- `logs/reduced_column_feasibility_20260718.md`
- `logs/reduced_column_feasibility_20260718.npz`
