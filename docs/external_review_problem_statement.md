# External Review Problem Statement: Dynamic Distillation Initialization

Date: 2026-07-07

## Purpose

We are seeking outside technical input on initialization and early dynamic stability for a rigorous dynamic distillation column model. The immediate question is whether the current initialization path is conceptually sound, what residual conditions should be required for acceptance, and whether the remaining instability points to the initializer or to the runtime condenser/top-drum coupling equations.

## Model Context

The model is a dynamic distillation column with explicit tray liquid and vapor holdups, optional tray energy states, hydraulic pressure coupling, top and bottom boundary states, and live or surrogate thermodynamics. Unlike a steady-state ChemSep-style model, the dynamic model includes explicit vapor inventory, pressure/vapor-flow closure, boundary vessel inventory, energy/temperature states, and controller interactions.

Imported ChemSep or Excel steady-state profiles are therefore treated only as seeds. They are not assumed to be dynamically consistent under this model's topology and RHS equations.

## Current Requirement Tension

The documentation distinguishes two targets, but this distinction needs review:

1. A mathematically consistent DAE initialization target: drive all relevant derivatives/residuals to zero at `t=0`.
2. A practical launch-seed target: reduce the dominant residuals enough that a short dynamic smoke run is stable and materially better than the raw seed.

The current implementation achieves the second target in short runs, but it does not yet produce a true zero-residual steady initial condition.

## What Was Tried

Several initializer strategies were explored:

- direct use of ChemSep/Excel steady state as a dynamic seed;
- residual-solver variants over vapor composition, vapor flow, liquid composition, energy, and boundary degrees of freedom;
- top-liquid/condensate composition alignment;
- vapor-equilibrium projection;
- liquid-plus-vapor equilibrium projection;
- vapor material-transport reconciliation;
- dynamic one-step scoring and ranking;
- an opt-in tray vapor linear-steady initializer.

Broad static residual minimization repeatedly proved misleading: it could reduce the optimizer objective while worsening the physical residual audit or the dynamic smoke test.

## Current Best Initializer Candidate

The most promising initializer is:

- `--init-align-tray-vapor-to-linear-steady`
- `--init-tray-vapor-linear-steady-scope interior`
- `--init-tray-vapor-linear-steady-blend 1.0`
- liquid/top alignment options used in the current C3/C4 launch recipe
- top-pressure control using `--pressure-control-mv top-anchor`
- a fixed top pressure anchor at `222.62 psia`

This initializer preserves tray vapor holdup totals and repacks tray vapor composition toward a local linear steady target implied by live vapor transport plus equilibrium source terms. It is not simply forcing `y = Kx`.

## Key Results

The linear-steady vapor initializer improved the one-step dynamic objective from about `27.28` to `6.18`. In a 10 s smoke run, the score decayed to about `1.30`.

The first 60 s extension initially failed because a real top-anchor pressure-ordering bug was discovered: an ordering guard could lift the tray pressure profile above the raw top-drum pressure even after an explicit top anchor had been applied. The RHS was corrected so an active explicit top anchor is used as the ordering reference. After this fix, the 60 s run passed:

- hydraulic top pressure stayed at `222.62 psia`;
- score decayed to about `0.560`;
- max relative state rate fell to about `0.00168 1/s`;
- vapor RHS audit at 60 s reported max relative vapor RHS about `0.000993 1/s`;
- energy/vapor closure showed `V_calc - V_used = 0` and negligible raw energy temperature rate.

The 300 s extension still failed, but the failure appears different. The run remains quiet through roughly 120 s, then fails around 140 s as the total-condenser/top-drum path surges:

- condensed flow jumps from about `8655 lbmol/h` to about `12245 lbmol/h`;
- top liquid net accumulation jumps to about `3885 lbmol/h`;
- raw top-drum pressure rises;
- pressure/vapor-flow inner correction grows rapidly.

Level-control diagnostics did not remove this onset:

- workbook true-level PV failed;
- forced molar-holdup PV failed;
- aggressive top molar-holdup tuning with `--top-level-kc 200 --top-level-ti 20` also failed.

This suggests the remaining 300 s failure is not simply weak level control and not necessarily an initializer failure. It may be a total-condenser/top-drum runtime coupling problem.

## Current Working Hypothesis

The initializer has become useful as a short launch seed, but it has not solved the full consistent initialization problem. The remaining long-run failure is likely caused by the generic total-condenser/top-drum coupling: condenser duty, condensed-flow calculation, raw top-drum pressure, and anchored hydraulic tray pressure are not fully compatible after the initial transient settles.

## Questions For Review

1. Should this model require a true zero-residual initialization before dynamic integration, or is a dynamically accepted launch seed an appropriate intermediate milestone?
2. Which residual blocks should be mandatory for acceptance, and what tolerances are reasonable?
3. Is the linear-steady vapor initializer a defensible approximation, or is it masking an equation defect?
4. Does the 300 s condenser/top-drum surge point to:
   - the initializer still leaving a hidden inconsistency,
   - total-condenser condensed-flow/duty equations,
   - top-drum pressure/vapor inventory coupling,
   - pressure-anchor semantics,
   - or controller/boundary-flow behavior?
5. Should the next fix target the condenser/top-drum equations before attempting another residual-solver initializer?

## Important Modeling Constraint

The implementation must remain generic. Code changes should not contain references to specific trays except for top and bottom boundary handling. The model is intended to support arbitrary column sizes and topologies.

## Most Relevant Artifacts In This Bundle

- `docs/requirements.md`
- `docs/initializer_requirements_and_acceptance.md`
- `docs/initializer_how_to_guide.md`
- `docs/initialization_code_status.md`
- `docs/dynamic_column_initialization_strategy.md`
- `docs/model_architecture.md`
- `docs/validation_readiness_gate_2026-05-26.md`
- `src/dynamic_distillation/column_rhs_v1.py`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- selected audit tools under `tools/`
- selected tests under `tests/`
- selected C3/C4 run summaries and audit reports under `logs/`
