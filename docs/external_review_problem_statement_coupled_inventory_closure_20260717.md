# External Review Problem Statement: Coupled Column Inventory Closure

Date: 2026-07-17

## Review Objective

Determine why the C3/C4 dynamic distillation model can appear dynamically
quiet while the total column inventory continues to decline, and recommend
the smallest physically defensible correction to the runtime formulation.

The central question is whether the present sequential explicit formulation
can be repaired locally, or whether pressure, vapor flow, phase generation,
energy, and liquid flow must be solved as a coupled algebraic/DAE block.

## Model Context

The model is a generic staged dynamic distillation column with:

- tray liquid and vapor component holdups as dynamic states;
- tray temperature/energy states;
- pressure and vapor-flow closure;
- Francis-weir liquid hydraulics;
- a total condenser with a reflux drum;
- a reboiler with a bottoms sump;
- live-composition product draws;
- feed flashing at feed-stage pressure and temperature;
- DWSIM Peng-Robinson thermodynamics;
- level, pressure, and bottoms-composition controllers.

The audited run used:

- explicit Euler integration with `dt = 0.2 s`;
- exponential composition-equilibrium relaxation with `tau = 0.5 s`;
- liquid-hydraulic blend `alpha = 0.25`;
- fixed reflux command near `5967.32 lbmol/h`;
- condenser pressure control through condenser duty;
- bottoms propane composition control through reboiler duty;
- condenser and reboiler duty limits of `65 MMBTU/h` magnitude.

The full command and all runtime settings are preserved in each included
`run_metadata_*.json` file.

## Primary Finding

The 2400-second continuation was previously accepted by a rate-based
steady-state gate:

| Quantity | Final value |
| --- | ---: |
| Feed, `F` | `7142.98 lbmol/h` |
| Distillate, `D` | `2983.79 lbmol/h` |
| Bottoms, `B` | `4692.97 lbmol/h` |
| `F - D - B` | `-533.79 lbmol/h` |
| Modeled `dM_total/dt` | `-533.79 lbmol/h` |
| Numerical mass-closure error | `-7.05e-12 lbmol/h` |
| Old steady-state score | `0.3804` (`PASS`) |

The arithmetic conservation law is working:

```text
dM_total/dt = F - D - B
```

The physical operating point is not steady. Product withdrawal exceeds feed
by about `7.5%` of feed, and the modeled inventory declines at the same rate.
Over the last 600 seconds, the mean inventory rate was about
`-549 lbmol/h`; this was not a momentary endpoint error.

The prior gate was therefore incomplete. It measured state-rate, KPI-slope,
manipulated-variable-rate, and temperature-rate criteria, but did not require
the whole-column material inventory rate to approach zero.

## Local Phase-Closure Experiment

An opt-in transport-balanced phase-transfer closure was implemented as a
diagnostic experiment. On each active tray it calculated the phase-transfer
rate needed to cancel the pre-equilibrium total vapor derivative.

For the matched one-step control and candidate:

| Result | Control | Candidate |
| --- | ---: | ---: |
| Summed active-tray pre-correction vapor rate | `-66.50 lbmol/h` | `-66.49 lbmol/h` |
| Summed post-correction vapor rate | `-66.50 lbmol/h` | numerical zero |
| Global inventory rate | `-530.81 lbmol/h` | `-530.81 lbmol/h` |
| Pressure, product rates, and duties | unchanged | unchanged |

The diagnostic closure did exactly what it was designed to do locally. It did
not improve the global material state.

After 60 simulated seconds, the candidate remained bounded and passed the old
gate with a score of `0.3735`, but:

- global inventory rate was still `-530.03 lbmol/h`;
- the closure generated about `352.77 lbmol/h` of vapor;
- the corresponding material was removed from tray liquid;
- combined tray-liquid depletion was about `534.76 lbmol/h`.

The experiment moved the residual between phases. It did not reconcile feed,
products, and total inventory. It is rejected as a production model path and
remains disabled by default.

## Why Local Cancellation Cannot Solve the Defect

For a tray total balance, using phase generation `E` as positive from liquid
to vapor:

```text
dML/dt = Lin - Lout + FL - E
dMV/dt = Vin - Vout + FV + E
```

Adding the equations eliminates `E`:

```text
d(ML + MV)/dt = Lin - Lout + Vin - Vout + FL + FV
```

Changing only `E` can redistribute inventory between liquid and vapor, but it
cannot change the total tray or whole-column material balance. This is exactly
what the probe demonstrated.

## Current Architectural Suspects

These are hypotheses for review, not yet proven root causes:

1. Vapor flow, pressure, phase generation, and energy are evaluated through
   sequential closures rather than one simultaneous local or global solve.
2. Liquid outflow still blends current Francis-weir hydraulics with imported
   profile ownership (`alpha = 0.25`), so liquid traffic is not fully owned by
   current inventory and geometry.
3. Vapor flow retains nominal-profile limiting
   (`dynamic_vflow_nominal_hi_ratio = 1.05`), which may prevent a physically
   required traffic correction.
4. Level controllers hold the terminal vessels near setpoint while excess
   product withdrawal is supplied by declining internal tray inventory. Quiet
   terminal levels therefore do not prove whole-column steady state.
5. The fast equilibrium process and slower transport/pressure processes may
   form a stiff coupled system that is not adequately represented by the
   present explicit sequential update.

## Established Corrections and Non-Issues

The external review should not reopen these without contrary evidence:

- Product component draws now use the live drum/sump compositions rather than
  fixed workbook component rates.
- Feed flashing is enabled at feed-stage conditions.
- DWSIM Peng-Robinson is the active thermo backend for these runs.
- Numerical global mass conservation is effectively exact.
- The rejected local closure is generic and not hardcoded to an interior tray.
- The runtime steady-state gate now includes:

```text
abs(dM_total/dt) / abs(F) <= 0.01
```

The gate-proof run reported `0.07375`, producing a corrected score of `7.3748`
and a `FAIL`.

## Questions for the Reviewer

1. Which existing equation or ownership boundary most plausibly sustains the
   observed `F - D - B` deficit while terminal levels remain controlled?
2. Should `P`, interstage `V`, phase generation `E`, energy, and possibly
   `L_out` be solved simultaneously at each time step?
3. Is a per-tray algebraic solve sufficient, or do pressure and countercurrent
   flows require a column-wide nonlinear solve?
4. Which states should remain differential, and which variables should become
   algebraic constraints in a DAE formulation?
5. Can the current exponential composition relaxation remain as a stable
   substep, or should phase equilibrium enter the algebraic system directly?
6. How should profile-derived flow limits be removed or homotopically retired
   without losing the bounded behavior already achieved?
7. What residual scaling, bounds, Jacobian strategy, and solver family would
   be appropriate for this hydrocarbon column?
8. What additional diagnostics would distinguish a flow-ownership defect from
   an insufficient integration/solver formulation?

## Required Acceptance Evidence

A proposed correction should be considered successful only if it:

1. is generic across all interior trays;
2. retains exact numerical component and total mass conservation;
3. reduces `abs(dM_total/dt)/F` below `0.01` and keeps it there;
4. does not merely transfer the residual between liquid and vapor;
5. keeps pressure, holdups, temperature, flows, and compositions bounded;
6. satisfies controller objectives without persistent saturation;
7. passes a short restart smoke test and an extended dynamic gate;
8. improves the result relative to the included 2400-second reference.

## Package Evidence

The package includes:

- this problem statement and a compact evidence table;
- the 2400-second reference summary/profile, report, metadata, restart
  workbook, and native checkpoint;
- matched one-step control and closure-candidate outputs;
- the 60-second closure probe;
- the corrected gate-proof output;
- current model source and focused tests;
- relevant requirements, architecture, gate, issue-log, and DD-060/DD-064
  documentation;
- the input workbook and initializer summary.

The 1.75 GB startup trace from the 2400-second run and the 42 MB trace from the
60-second probe are intentionally excluded. Their compact CSV outputs,
metadata, and checkpoints are included.
