# Reviewer Prompt: Dynamic Distillation Coupled-Closure Problem

You are being asked to perform an independent, equation-level technical review
of a dynamic distillation model. The objective is not merely to improve a
numerical score. It is to identify why the model can become dynamically quiet
while remaining materially unsteady, and to recommend a physically rigorous,
generic correction.

Please use the attached artifact package:

`external_review_coupled_inventory_closure_20260717.zip`

Start with:

1. `PROBLEM_STATEMENT.md`
2. `EVIDENCE_SUMMARY.csv`
3. `docs/dd_064_global_inventory_gate_and_phase_closure_probe_20260717.md`
4. `docs/dd_060_physics_owned_tray_flow_probe_20260712.md`
5. `source/dynamic_distillation/column_rhs_v1.py`
6. `source/dynamic_distillation/dynamic_run_scaffold_v1.py`

Use the raw CSVs, metadata, checkpoints, tests, and source to verify the
claims. Do not rely only on the problem statement or README.

## System Being Reviewed

The application is a generic staged dynamic distillation simulator. Its main
runtime model includes:

- liquid and vapor component holdups on each tray;
- temperature and energy states;
- tray pressure and interstage vapor-flow calculations;
- equilibrium relaxation;
- Francis-weir liquid hydraulics;
- a total condenser and reflux drum;
- a reboiler and bottoms sump;
- live-composition product draws;
- feed flashing at feed-stage conditions;
- geometry-based terminal level measurements;
- pressure, level, and bottoms-composition controllers;
- DWSIM Peng-Robinson thermodynamics.

The audited C3/C4 case uses explicit Euler integration at `dt = 0.2 s`,
composition-exponential equilibrium relaxation with `tau = 0.5 s`, and a
liquid-hydraulic blend of `alpha = 0.25`.

Interior-stage logic must remain generic. Any stage-specific exception is
unacceptable unless it represents actual top or bottom equipment topology.

## Central Problem

The 2400-second reference continuation was reported as steady by the original
rate-based gate:

```text
steady_state_score = 0.3804
steady_state_flag  = PASS
```

Its final overall material state was:

```text
F = 7142.98 lbmol/h
D = 2983.79 lbmol/h
B = 4692.97 lbmol/h

F - D - B = -533.79 lbmol/h
dM_total/dt = -533.79 lbmol/h
global numerical mass-closure error = approximately 7e-12 lbmol/h
```

The numerical conservation identity is essentially exact, but the operating
point is not at material steady state. Products exceed feed, and internal
column inventory supplies the difference. The deficit persisted through the
final 600 seconds rather than appearing only at the endpoint.

The original gate did not test whole-column inventory rate. A new criterion
now requires:

```text
abs(dM_total/dt) / abs(F) <= 0.01
```

The audited state is near `0.074`, so the corrected gate rejects it.

## Diagnostic Closure Experiment

An opt-in transport-balanced phase-transfer closure was implemented only as a
probe. For each active tray, it added the equal-and-opposite phase-transfer
rate required to cancel the tray's pre-equilibrium total vapor derivative.

In a matched one-step comparison:

- the control retained about `-66.50 lbmol/h` summed tray vapor rate;
- the candidate reduced that vapor rate to numerical zero;
- pressure, duties, feed, products, and global inventory rate did not change;
- global inventory still declined at about `-530.81 lbmol/h`.

After 60 simulated seconds:

- the run remained bounded;
- the old gate still passed with a score near `0.374`;
- global inventory still declined at about `-530.03 lbmol/h`;
- the probe generated about `352.77 lbmol/h` of vapor;
- an equal amount was removed from liquid;
- combined tray-liquid depletion was about `534.76 lbmol/h`.

The probe therefore moved the residual between phases rather than correcting
the whole-column material state. It is disabled by default and rejected as a
production solution.

## Relevant Balance Structure

Using `E` as positive phase generation from liquid to vapor, the tray-total
balances have the conceptual form:

```text
dML/dt = Lin - Lout + FL - E
dMV/dt = Vin - Vout + FV + E
```

Adding them eliminates `E`:

```text
d(ML + MV)/dt = Lin - Lout + Vin - Vout + FL + FV
```

This explains why changing only the phase-transfer term cannot correct total
inventory. Please verify how the implemented component, phase, energy, and
boundary equations correspond to these conceptual balances.

## Findings Already Established

Treat the following as established unless the attached evidence disproves
them:

1. Total and component mass accounting closes numerically to roundoff.
2. The reference state is materially unsteady despite its low old-gate score.
3. Product component draws use current drum/sump composition rather than fixed
   workbook component rates.
4. Feed flashing is enabled at feed-stage pressure and temperature.
5. DWSIM Peng-Robinson is the active property method for these runs.
6. The local transport-balanced phase-transfer probe cannot repair the global
   inventory deficit.
7. The new global-inventory gate correctly rejects the tested state.
8. Earlier UV-equilibrium probes found incompatible pressure ownership between
   hydraulic pressure, vapor-holdup-implied pressure, and local UV equilibrium
   pressure.

## Hypotheses Requiring Independent Review

Do not assume these are correct. Test them against the code and data:

1. Pressure, vapor flow, phase generation, and energy are solved sequentially
   when they should be one coupled algebraic block.
2. The retained liquid profile blend (`alpha = 0.25`) prevents current
   inventory and geometry from fully determining liquid outflow.
3. The vapor nominal-profile limiter
   (`dynamic_vflow_nominal_hi_ratio = 1.05`) may suppress physically required
   vapor-traffic correction.
4. Terminal level controllers can remain near setpoint while internal tray
   inventory drains, hiding whole-column material motion.
5. The `tau = 0.5 s` equilibrium process coupled to slower transport and
   pressure dynamics creates stiffness that is poorly handled by the current
   explicit sequential update.
6. Pressure and explicit vapor holdup currently act as competing owners of the
   same thermodynamic state.

## Requested Analysis

### 1. Independently Verify the Evidence

Recalculate, from the included CSVs:

- final and time-window `F - D - B`;
- modeled total-inventory rate;
- numerical closure error;
- old and corrected steady-state scores;
- one-step control-versus-candidate vapor residuals;
- liquid and vapor phase-rate redistribution in the 60-second probe;
- trends in terminal levels, internal inventory, pressure, duties, and product
  rates.

State clearly whether the evidence supports a persistent structural issue, a
long but ordinary transient, controller behavior, or some combination.

### 2. Audit Equation Ownership

Trace every owner and writer of:

- tray liquid component holdup;
- tray vapor component holdup;
- total tray liquid and vapor inventory;
- tray pressure;
- interstage vapor flow;
- tray liquid outflow;
- phase generation/condensation;
- temperature and energy;
- condenser and reboiler phase transfer;
- reflux, distillate, boilup, and bottoms rates.

Identify duplicated, lagged, blended, overridden, or mutually inconsistent
owners. Cite exact files, functions, and line numbers.

### 3. Audit Material and Energy Equations

For interior trays and each terminal boundary:

- write the implemented component and total balances;
- check signs, units, and time-basis conversions;
- verify that phase transfer cancels from total material;
- verify that latent heat and phase generation use one consistent basis;
- identify clamps, guards, profile blends, or projections that can make one
  equation inconsistent with another;
- determine whether pressure and vapor holdup satisfy a common volume/EOS
  constraint.

Distinguish an accounting defect from a physically valid inventory transient.

### 4. Assess the Numerical Formulation

Decide whether the current explicit sequential formulation is mathematically
appropriate for the coupled system.

Please compare at least these alternatives:

1. retain the current ODE formulation with targeted corrections;
2. add a per-tray implicit nonlinear closure;
3. solve a column-wide algebraic block at every time step;
4. reformulate as an index-1 DAE;
5. use conserved component totals and internal energy as differential states,
   with a UV/volume equilibrium solve for phase split, temperature, pressure,
   and compositions.

For each credible alternative, describe:

- differential states;
- algebraic unknowns;
- algebraic residuals;
- coupling across neighboring trays;
- handling of top and bottom equipment;
- Jacobian structure;
- expected stiffness;
- suitable solver families;
- likely implementation and validation risk.

### 5. Recommend the Smallest Defensible Fix

Provide a specific recommendation rather than only a conceptual diagnosis.
The recommendation should answer:

- Is a broader simultaneous solve required?
- Can it be introduced incrementally?
- Which existing states or equations should be retired?
- Which profile-derived limits should be retained temporarily, ramped out, or
  removed?
- How should Francis hydraulics become fully physics-owned?
- How should equilibrium be enforced without introducing a nonphysical phase
  source?
- How should pressure and vapor holdup be reconciled?
- How should controllers interact with the revised model?

Include equations, residual definitions, variable bounds, scaling guidance,
and pseudocode detailed enough to guide implementation.

### 6. Propose a Phased Implementation Plan

Please separate the work into small, falsifiable stages. A useful plan might
include:

1. a read-only residual/audit tool;
2. an offline nonlinear solve at an existing checkpoint;
3. a one-step implicit pilot;
4. a short dynamic A/B comparison;
5. retirement of profile ownership;
6. an extended controlled run.

For every stage, specify:

- exact purpose;
- variables solved;
- success/failure metrics;
- tests required;
- stop criteria that would prevent another unproductive tuning exercise.

### 7. Define Acceptance Tests

At minimum, propose tests for:

- per-component and total mass conservation;
- energy conservation;
- volume/EOS consistency;
- pressure/vapor-flow consistency;
- phase-equilibrium consistency;
- positivity and boundedness;
- top and bottom equipment balances;
- feed-stage balance without stage-specific code;
- controller saturation and setpoint tracking;
- checkpoint/restart parity;
- dynamic timestep sensitivity;
- whole-column inventory convergence;
- short and extended dynamic gates.

## Constraints

Any proposed correction must:

- remain generic for arbitrary tray counts and feed locations;
- avoid hardcoded references to particular interior trays;
- preserve top/bottom exceptions only where actual equipment topology differs;
- use live state compositions for physical product draws;
- retain feed flashing at stage conditions;
- retain DWSIM PR as the validation thermo baseline;
- conserve each component and total material to numerical precision;
- include energy and volume consequences of phase change;
- prevent negative or nonfinite pressure, temperature, flow, or holdup;
- avoid accepting a state merely because derivatives are small;
- avoid hiding the problem with stronger relaxation, clamps, controller tuning,
  or profile forcing.

Do not recommend tuning the rejected local phase-transfer closure.

## Expected Response Format

Please structure the response as follows:

1. **Executive conclusion**
   - Is the model architecture fundamentally repairable?
   - Is the current problem primarily equations, numerical formulation,
     control, or a mixture?
   - Is a coupled algebraic/DAE solve warranted?

2. **Verified findings**
   - Findings ordered by severity.
   - Exact code and artifact citations.
   - Separate confirmed defects from hypotheses.

3. **Equation-level diagnosis**
   - Implemented balances and ownership conflicts.
   - Explanation of the observed inventory loss.

4. **Recommended formulation**
   - Differential states, algebraic variables, and residual equations.
   - Solver and scaling recommendations.

5. **Implementation plan**
   - Smallest first experiment.
   - Phased changes with explicit stop/go gates.

6. **Validation plan**
   - Unit, equation, integration, restart, and long-run tests.
   - Quantitative acceptance thresholds.

7. **Risks and alternatives**
   - What could invalidate the recommendation?
   - What evidence would justify staying with the present ODE architecture?

8. **Bottom line**
   - A direct recommendation to stay the course, pivot to a coupled
     formulation, or stop development pending a larger redesign.

Please be candid. If the evidence is insufficient to identify the root cause,
name the exact missing diagnostics or artifacts needed. If you find a simpler
equation defect that avoids a DAE reformulation, demonstrate why it explains
all included evidence and how it should be tested.
