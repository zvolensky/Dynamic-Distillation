# DD-067: Conservative Energy Redistribution Probe

Date: 2026-07-17

## Question

DD-066 showed that the frozen 2400-second C3/C4 checkpoint is locally valid
but globally incompatible: its independent top and bottom UV closures imply
reversed pressure ordering. The external review recommended allowing local
conserved states to move while preserving whole-column component and energy
totals.

DD-067 asks the narrowest useful question first:

> Can pressure ordering be recovered by redistributing only internal energy,
> while keeping every node component inventory and volume fixed and preserving
> exact whole-column energy?

Hydraulic flow equations are deliberately excluded from this first probe.

## Formulation

The physical node sequence contains:

- one combined total-condenser/reflux-drum assembly;
- 18 interior trays;
- one combined partial-reboiler/bottoms-sump assembly.

For each node, component inventory and fixed volume remain equal to the
checkpoint values. A weighted isotonic projection creates a nondecreasing
top-to-bottom pressure profile with a `0.01 psi` minimum increment. At each
trial pressure, a bounded local solve determines temperature and vapor
fraction from volume and TP-equilibrium closure. A uniform pressure shift is
then solved so that the sum of implied node internal energies equals the
checkpoint whole-column energy.

This is an existence probe. It minimizes weighted pressure movement, not
conserved-state movement, and it is not the final least-movement initializer.

## Result

The limited pressure/energy feasibility gate passes:

| Metric | Result |
|---|---:|
| Component conservation error | `0 lbmol` |
| Whole-column energy error | `-0.0295 BTU` |
| Whole-column relative energy error | `1.84e-9` |
| Fixed-pressure node closures | `20 / 20` |
| Accepted bound solutions | `0` |
| Maximum volume relative residual | `3.34e-8` |
| Maximum component reconstruction relative residual | `2.63e-10` |
| Maximum equilibrium-beta residual | `3.57e-10` |

The repaired pressure endpoints are:

```text
top terminal     210.650 psia
bottom terminal  228.414 psia
```

The construction requires substantial movement:

| Movement metric | Result |
|---|---:|
| Energy moved, half L1 | `747,127 BTU` |
| Energy L1 change | `1,494,254 BTU` |
| Energy L1 fraction of checkpoint inventory | `9.32%` |
| Maximum node energy change | `536,480 BTU` |
| Maximum node specific-energy change | `1,854.5 BTU/lbmol` |
| Maximum pressure change | `93.66 psi` |
| Pressure RMS change | `49.30 psi` |

The largest pressure correction is at tray 2, from `321.89` to about
`228.23 psia`. The largest energy correction is the bottom terminal assembly,
which gains about `536,480 BTU`. Upper interior trays generally lose energy
while the lower column and bottom terminal gain it.

## Interpretation

This is real progress:

- the terminal pressure reversal is not a proof that no conservative state
  exists;
- no component transfer is required to produce at least one ordered local UV
  state;
- whole-column energy can be preserved to numerical precision.

It is not an accepted initialization:

- the pressure profile is largely flattened by the isotonic objective;
- the profile has not satisfied pressure-drop, vapor-flow, liquid-flow, or
  terminal flow equations;
- the reported `9.32%` energy movement is not a minimum because this probe did
  not optimize `Delta U`;
- local TP-flash beta consistency is not a direct fugacity residual.

The frozen checkpoint is therefore repairable in a mathematical sense, but
this particular construction is too intrusive and hydraulically incomplete
to serialize as a dynamic seed.

## Decision

Stay the course, with a disciplined next step:

1. formulate a globally conservative least-movement solve that allows local
   `Delta N_i,k` and `Delta U_i`;
2. enforce exact whole-column component and energy conservation, positivity,
   fixed volumes, local UV closure, and pressure ordering;
3. minimize scaled conserved-state movement from the checkpoint and compare
   its movement with DD-067;
4. only after that solve is robust, add the uncapped hydraulic pressure-drop
   and vapor-flow residual;
5. do not change the production RHS or call the result an initializer until
   the hydraulic and terminal closure gates pass.

## Evidence

- `src/dynamic_distillation/conservative_checkpoint_redistribution_v1.py`
- `tools/solve_conservative_checkpoint_redistribution.py`
- `tests/test_conservative_checkpoint_redistribution_v1.py`
- `logs/conservative_checkpoint_redistribution_20260717.json`
- `logs/conservative_checkpoint_redistribution_20260717.md`
