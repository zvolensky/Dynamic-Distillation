# DD-068: Least-Movement Conserved-State Redistribution

Date: 2026-07-17

## Question

DD-067 proved that whole-column energy can be redistributed to recover an
ordered local UV pressure profile, but its pressure-isotonic construction was
not a minimum-movement solution and did not include hydraulics.

DD-068 asks:

> Can a globally conservative redistribution of component inventory and
> internal energy find a robust, materially smaller ordered local-UV state
> before the hydraulic network is added?

This is still an algebraic diagnostic. It does not use liquid or vapor
hydraulics, runtime profile forcing, controller equations, or dynamic
integration.

## Formulation

The solve uses the same 20 physical nodes as DD-067:

- one combined total-condenser/reflux-drum assembly;
- 18 interior trays;
- one combined partial-reboiler/bottoms-sump assembly.

The primary objective is normalized L2 movement in local component inventory
and internal energy:

```text
minimize sum((Delta N / N_scale)^2) + sum((Delta U / U_scale)^2)
```

The constraints enforce:

- exact whole-column conservation of every component;
- exact whole-column internal-energy conservation;
- positive local component inventories;
- fixed node volumes;
- converged local UV closure at every accepted state;
- nondecreasing pressure from top to bottom with a `0.01 psi` increment.

The implementation uses sequential linearization of local pressure
sensitivities followed by nonlinear UV reevaluation and line search. L1 and
Huber movement are reported as diagnostics, but they do not determine the
accepted solution.

Five starts were attempted:

- frozen checkpoint;
- DD-067 result;
- linear pressure profile;
- small conservative random perturbation;
- moderate conservative random perturbation.

## Result

Two starts converged to the same local basin:

| Start | Normalized L2 objective |
|---|---:|
| Checkpoint | `0.4962840773` |
| Random moderate | `0.4962840798` |

Their relative objective spread is `2.57e-9`, well below the requested
`1e-4` reproducibility tolerance. The DD-067, linear-pressure, and
random-small starts did not pass all convergence gates. This is evidence for
a reproducible local minimum candidate, not proof of a robust global minimum.

The best result preserves the global conserved quantities to numerical
precision and passes all local UV closures without active bounds:

| Metric | Result |
|---|---:|
| Normalized L2 objective | `0.4962841` |
| Component contribution | `0.2629940` |
| Energy contribution | `0.2332901` |
| Relative energy conservation error | `2.90e-17` |
| Linearized first-order optimality estimate | `1.42e-12` |
| Constraint violation norm | `9.10e-7` |
| Active bounds | `0` |
| Local UV evaluations | `1620` |

The required movement remains large:

| Movement metric | Result |
|---|---:|
| Material moved, half L1 | `68.8648 lbmol` |
| Energy moved, half L1 | `1,012,849 BTU` |
| Energy movement relative to DD-067 | `1.356` |
| Maximum pressure change | `79.159 psi` |
| Maximum pressure change relative to DD-067 | `0.845` |
| Pressure RMS change | `44.120 psi` |
| Terminal share of absolute component movement | `31.5%` |
| Terminal share of absolute energy movement | `80.3%` |

The ordered endpoint pressures are approximately:

```text
top terminal     182.566 psia
tray 2           242.732 psia
bottom terminal  242.912 psia
```

The top-to-first-tray jump is therefore about `60 psi`, while the interior
profile is almost flat. The top terminal loses about `858,620 BTU` and the
bottom terminal gains about `768,354 BTU`.

## Interpretation

DD-068 is informative but does not justify adding hydraulics:

- normalized L2 redistribution finds a repeatable local basin from two
  independent starts;
- the reported stationarity is for the final sequentially linearized
  subproblem, not a proof of a global nonlinear optimum;
- three of five starts fail, so the solve is not globally robust;
- energy movement is larger than DD-067 rather than materially smaller;
- the maximum pressure correction improves by only about `15.5%`;
- terminal assemblies absorb `80.3%` of absolute energy movement;
- the pressure shape remains physically suspicious.

The result changes the next diagnostic target. The main question is no longer
whether an ordered conservative local state exists. It does. The question is
why the checkpoint-to-conserved-state mapping requires terminal energy
reallocation and a top/interior pressure jump of this size.

The already completed DD-065 controller degree-of-freedom audit passed and is
not an open prerequisite.

## Decision

Classification: `dd068_stop_before_hydraulics`.

Do not:

- add the hydraulic network to this candidate;
- serialize it as an initializer;
- modify the production RHS to accommodate it;
- launch dynamic settling from it.

Next audit:

1. recheck reflux-drum, condenser, reboiler, and sump energy ownership;
2. verify stage and terminal fixed-volume bases, including vapor-space volume;
3. verify the `U = H - P*V` conversion and pressure units for every owner;
4. determine why the top terminal and first interior tray imply such different
   pressures;
5. rerun DD-068 only after a concrete mapping or volume defect is corrected.

If those audits confirm the present mapping, stop pursuing checkpoint repair
as the production initializer path and formulate the full steady-state
conserved-state solve from operating specifications instead.

## Evidence

- `src/dynamic_distillation/least_movement_redistribution_v1.py`
- `tools/solve_least_movement_checkpoint_redistribution.py`
- `tests/test_least_movement_redistribution_v1.py`
- `logs/least_movement_checkpoint_redistribution_20260717.json`
- `logs/least_movement_checkpoint_redistribution_20260717.md`
