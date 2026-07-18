# Gates Explained

## Purpose

A gate is an explicit pass/fail or proceed/hold decision based on measured model behavior.

In this project, gates are needed because a dynamic distillation run can look acceptable by one metric while still being physically or numerically unhealthy by another. For example:

- a seed can reduce static residuals but blow up dynamically,
- a run can pass a rate-based steady-state score while an internal liquid inventory is slowly draining,
- a run can look quiet while `K_state` drifts away from live thermo `K_thermo`,
- a startup sequence can become unstable if liquid or vapor hydraulics are turned on too abruptly.
- a controlled run can be quiet and mass-conserving while imported flow profiles or incompatible pressure states still own part of the solution.

Gates keep those cases from being treated as accepted results just because one diagnostic improved.

## Simple Definition

A gate answers one of these questions:

- Should this candidate be accepted?
- Should this startup ramp continue, pause, or back off?
- Should this run be called healthy?
- Should this case be used for validation?
- Should a diagnostic result be promoted to a saved/restartable artifact?

The important point is that a gate is not the model equation itself. It is a decision layer around the model or around a staged runtime procedure.

## Why Gates Are Needed

Dynamic column simulations have coupled fast and slow behavior:

- material balances,
- liquid/vapor holdups,
- pressure and vapor flow,
- equilibrium/K-value tracking,
- energy and temperature,
- boundary vessels,
- controllers,
- feed flashing and product draws.

Improving one block can make another block worse. A gate forces the workflow to ask, "Did the whole run become more usable, or did we only move the problem?"

This matters especially for initialization. A steady-state Excel or ChemSep profile is only a seed. It is not automatically a model-consistent dynamic initial condition. The initializer therefore needs both:

- residual gates at `t=0`, and
- dynamic smoke gates after a short run.

## Main Gate Types In This Repository

### 1. Residual Gates

Residual gates check whether the initial state is consistent with the model RHS at `t=0`.

They look at quantities such as:

- tray liquid residuals,
- tray vapor residuals,
- top and bottom boundary residuals,
- pressure/vapor-flow closure,
- energy and temperature residuals,
- feed-stage consistency.

Primary tool:

- `tools/column_initialization_residual_audit.py`

Typical use:

- reject an initializer candidate if its `t=0` residuals are too large,
- identify which block is responsible for the mismatch,
- guide targeted least-squares or reconciliation work.

Limitation:

- passing a residual gate is necessary but not sufficient. A seed can have improved static residuals and still behave worse dynamically.

### 2. Dynamic Smoke Gates

Dynamic smoke gates run the model for a short time and ask whether the candidate behaves acceptably after launch.

They measure fields from `column_summary_*.csv`, including:

- `steady_state_score`,
- `ss_max_rel_state_rate_per_s`,
- `ss_max_temp_rate_F_per_s`,
- pressure/vapor-flow inner-solve diagnostics,
- top/bottom boundary imbalance diagnostics,
- K-state/K-thermo diagnostics when present.

Primary tool:

- `tools/evaluate_initialization_dynamic_gate.py`

Typical use:

- compare an initializer candidate against a baseline run,
- reject a candidate that improves residuals but worsens dynamic behavior,
- report the dominant reason for failure.

This is why initializer acceptance is not based on least-squares residual reduction alone.

A dynamic smoke gate should not rely on a single lucky checkpoint. For long or oscillatory runs, it should also check the final-window trend. A candidate that briefly passes and then turns upward again should remain provisional until the later behavior is understood.

### 3. Steady-State Score Gate

The runtime writes a rate-based steady-state score into the summary CSV:

- `steady_state_score`,
- `steady_state_flag`,
- `ss_max_rel_state_rate_per_s`,
- `ss_max_temp_rate_F_per_s`,
- `ss_global_inventory_rate_frac_feed`,
- related fields identifying the worst state, stage, and component.

Primary implementation:

- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Typical use:

- decide whether the run is dynamically quiet over the current window,
- compare run recipes,
- provide a compact health indicator in logs.

Important limitation:

- this is mostly a rate gate. It can miss level or consistency problems such as slow K-state drift or slow liquid inventory depletion. That is why additional gates now exist.
- the runtime now also rejects a nominal steady-state result when the absolute whole-column inventory rate exceeds `1%` of feed by default. This prevents a quiet run with `D + B` materially different from `F` from passing merely because the loss is distributed across many state variables.

### 4. Normalized Equilibrium-Target Gate

This gate checks whether the integrated vapor composition remains consistent with the normalized equilibrium target actually used by the model.

It asks whether:

- live `y` remains close to normalized `y_target`,
- the mismatch is growing,
- the final mismatch is physically meaningful.

Primary tool:

- `tools/audit_k_state_drift.py`

Typical use:

- reject a run that looks quiet by rate metrics but is drifting away from thermo consistency,
- distinguish a truly healthy dynamic run from a merely slow-moving inconsistent run.

Raw `K_state = y/x` must not be compared directly with raw thermo `K` unless `sum(K*x)=1`. In the general normalized target, `y_i/x_i = K_i/sum(K*x)`. The tool retains raw-K fields as diagnostic context, excludes generic terminal states by default, and gates interior normalized `y-y_target` consistency.

### 5. Liquid Inventory Depletion Gate

The liquid-inventory gate checks whether any internal tray is slowly draining toward a low-holdup condition.

It watches:

- minimum internal tray liquid inventory,
- inventory update fraction per logged step,
- large composition steps caused by low inventory,
- persistent differences between marched liquid flow and hydraulic liquid flow when logged.

Primary tools:

- `tools/audit_liquid_inventory_depletion.py`
- `tools/audit_feed_stage_equations.py`

Typical use:

- reject a run that appears calm but is heading toward an eventual composition snap,
- identify profile-flow recipes where `L_out_used` is not following the hydraulic candidate `L_out_hyd`,
- distinguish terminal vessel level behavior from internal tray dryout.

This gate is now especially important after the liquid-hydraulic flow ownership finding.

### 6. Startup Sequence Gates

Startup gates control whether a staged handoff should proceed.

The runtime can hold, ramp, or back off liquid and vapor handoff based on residual or rate thresholds.

Relevant configuration and implementation:

- `--enable-startup-hydraulic-sequence`
- `--startup-sequence-mass-resid-gate-lbmolph`
- `--startup-sequence-vapor-rel-rate-gate-per-s`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Typical use:

- start from profile-like traffic,
- delay or ramp liquid hydraulics,
- delay or ramp vapor/energy closure,
- prevent abrupt activation of stiff coupled dynamics.

These gates are procedural. They do not say the final run is valid; they only control how aggressively the runtime transitions from seeded/profile behavior to live dynamic behavior.

### 7. Physical Equation Gates

Some gates live inside the model equations as physical guards.

Example:

- top-drum pressure gate in `src/dynamic_distillation/column_rhs_v1.py`
- diagnostics such as `V_to_top_drum_pressure_gate_scale`

Purpose:

- prevent physically impossible reverse vapor slip,
- taper or block a flow when the driving force has the wrong sign,
- keep boundary coupling directionally consistent.

These are different from acceptance gates. They are part of the model's physical/numerical formulation.

### 8. Validation Readiness Gate

Validation readiness gates decide whether a case is mature enough to call "validated."

Primary document:

- `docs/validation_readiness_gate_2026-05-26.md`

Typical criteria:

- topology match is explicit,
- phase material balances are meaningful,
- feed treatment is consistent,
- thermo basis is consistent,
- startup does not alter the validation seed,
- energy closure is acceptable,
- K-state drift is controlled,
- internal liquid inventories remain buffered.

This is the highest-level gate. It prevents a diagnostic pass from being overstated as full rigorous dynamic validation.

### 9. Physical Closure Gate

The physical-closure gate asks whether the final operating profile is actually determined by one internally consistent equation set.

It checks at least:

- `L_out_used` is owned by active hydraulics rather than a nonzero blend with an imported profile,
- net tray evaporation or condensation is coupled to component and total-energy conservation,
- hydraulic pressure agrees with pressure implied by vapor holdup, vapor volume, temperature, composition, and Z,
- vapor-flow profile caps or imported nominal traffic are not binding at the accepted operating point,
- feed and boundary flows explain section-to-section material changes without replacing interior phase physics.

DD-058 demonstrates why this gate is separate from the dynamic score. DD-058 is quiet, controlled, and mass-conserving, but its section-wise liquid-flow plateaus are partly imposed by profile blending and fixed phase totals. DD-060 demonstrates why simply enabling full TP-flash phase relaxation is not sufficient: phase-total changes must also conserve energy.

Current status:

- DD-058: operational dynamic gates pass; rigorous physical-closure gate fails.
- DD-060 `phase-exponential`: experimental diagnostic; physical-closure and dynamic gates fail.
- DD-065: all active interior trays pass local UV closure, but the global pressure/vapor-flow solve fails.
- DD-066: terminal checkpoint inventories are fully accounted, but independent terminal UV closure implies `P_bottom-P_top=-13.95 psi`; frozen terminal states cannot be coupled unchanged into a physical upward-vapor-flow network.
- DD-067: energy-only conservative redistribution can produce ordered local UV pressure with exact whole-column conservation, but the pressure-isotonic construction moves `9.32%` of energy inventory on an L1 basis and excludes hydraulics; feasibility therefore passes while initializer acceptance remains blocked.
- DD-068: normalized L2 component-and-energy redistribution finds one local basin from two independent starts, but three of five starts fail, energy movement is `1.356` times DD-067, maximum pressure movement remains `79.159 psi`, and terminal assemblies absorb `80.3%` of absolute energy movement; the robustness and movement gates therefore stop the workflow before hydraulics.
- DD-069: `U=H-PV`, phase aggregation, mapped-U provenance, and empty-placeholder invariance pass, but sump fixed-volume reconstruction misses by `51.47%`, representative interior controls miss volume by `17%` to `38%`, stored-H mismatch reaches `233%`, and normalized energy-movement cost varies by a factor of `4134.77`; correct these bases before repeating redistribution.
- DD-070: canonical live-property energy, neutral whole-column scaling, and a liquid-only sump reduce the best energy movement to `159,739 BTU` and maximum pressure correction to `23.335 psi`, but only one of five starts converges and the checkpoint enthalpy mismatch is state-dependent; the bounded retry fails and checkpoint repair is retired.
- DD-071 registry: separate reboiler and sump states produce `291` unknowns and `290` residuals because their connecting liquid outlet has no owner. A combined conserved bottom control volume produces a square, structurally full-rank `281 x 281` registry with no empty rows, unused columns, or missing owners.
- DD-072 numerical gate: all `281` direct residuals evaluate with live DWSIM PR at the ChemSep, bounded-perturbation, and checkpoint guesses. Component and energy equations telescope near machine precision. ChemSep and perturbed Jacobians retain rank `281` at `h` and `h/2`, and an uncolored reference finds zero numerical dependencies outside the registry graph. The condition estimate remains high (`1.3e8` at ChemSep and up to `2.4e9` at the perturbation), so this authorizes bounded staged continuation only.
- DD-073 continuation gate: the approved `160/240/258/277/281` transformed continuation is implemented, but two live DWSIM PR paths stop in Stage 1 while retaining full rank and exact conservation. Direct Stage 1 endpoint diagnostics also leave an approximately `2.1e-4` scaled residual floor. Holding ChemSep-derived conserved `N/U` fixed while reconciling phase states is therefore not an accepted first stage. Release ordering must change before another full continuation.
- DD-074 merged-stage gate: the final release-order redesign produces the exact `240/258/277/281` counts, identity anchors, exact DD-072 endpoints, and machine-precision conservation. The merged `240 x 240` physical block has structural rank `239`, however, so the gate blocks a live solve and retires manual staged continuation.
- UV/DAE architecture: local conserved-state viability and terminal bookkeeping are demonstrated; global hydraulic and terminal-equation closure remain unaccepted.

### 9.1 Local Thermodynamic Closure Gate

For each conserved tray state, solve temperature, pressure, phase split, and
equilibrium compositions from total component inventory, total internal
energy, and fixed volume.

Default rigorous targets are:

- component reconstruction relative residual `<1e-8`;
- energy relative residual `<1e-7`;
- volume relative residual `<1e-7`;
- fugacity residual or documented backend-certified equivalent `<1e-6`;
- no negative phase amounts;
- no accepted projection.

A TP-flash beta consistency residual may be reported when fugacity coefficients
are unavailable, but it must not be labeled as a fugacity residual.

### 9.2 Global Hydraulic Closure Gate

After local closure, solve the pressure-drop and vapor-flow network without
imported profile ownership or previous-step limits determining the answer.

Default rigorous targets are:

- scaled pressure-drop and vapor-flow residuals `<1e-5`;
- local-thermo versus global solved-pressure mismatch `<0.1 psi`;
- zero binding profile/previous-step flow limiters;
- zero accepted projections;
- materially identical convergence from at least `+/-10%` pressure and flow guesses.

DD-065 demonstrates why this gate is separate: local UV closure passed, but
the implied pressure profile ran in the wrong overall direction and the global
network could not close.

### 9.3 Terminal-Equipment Closure Gate

The condenser, reflux drum, reboiler, and sump must preserve every component,
energy, and volume inventory required by their selected topology. Omitted
resident vapor or virtual terminal-stage inventory is a gate failure, not a
small reporting discrepancy.

### 9.4 Conservative Redistribution Gate

Before a redistributed conserved state is passed to the hydraulic network:

- every component and whole-column internal energy must remain conserved;
- all accepted local UV states must pass without active projection;
- materially different initial guesses must reproduce the accepted basin;
- normalized L2 movement is the primary objective, with L1 and Huber movement
  reported for interpretation;
- per-node donors, receivers, sign reversals, pressure movement, and
  terminal-versus-interior movement shares must be reported;
- large terminal concentration of movement or a large terminal-to-interior
  pressure discontinuity blocks hydraulic continuation.

DD-068 demonstrates this stop gate. Local feasibility and a stationary
objective are not enough when only two of five starts converge and the
terminal assemblies carry most of the energy correction.

### 9.5 Energy, Volume, And Scaling Basis Gate

Before interpreting a conservative redistribution:

- reconstruct `H`, `PV`, and `U=H-PV` with explicit units and provenance;
- verify fixed control volume equals reconstructed liquid plus vapor volume;
- compare checkpoint stored phase enthalpy with live property reconstruction;
- verify combined and phase-summed internal energy agree;
- prove an eliminated zero-inventory placeholder changes no conserved total
  or physical volume;
- report the normalized objective cost of the same physical energy move at
  terminal and interior nodes.

DD-069 demonstrates why this gate is needed. The algebraic `PV` conversion is
correct, but the checkpoint phase states and DD-068 scaling are not neutral
inputs to a physical least-movement interpretation.

### 9.6 Bounded Repair Retirement Gate

A checkpoint-repair branch must define its retry count and pass criteria
before execution. Canonical mapping replacement is reported separately from
optimizer movement. A failed bounded retry may not be converted into an
unlimited tuning campaign.

DD-070 demonstrates this gate. Corrected mapping and neutral scaling improved
the magnitude of the candidate, but did not produce a reproducible solve.
Checkpoint repair is therefore retired and the workflow advances to a direct
steady-state conserved formulation.

### 9.7 Registry And Structural-Rank Gate

Before numerical residual evaluation or solver tuning:

- register every unknown and residual deterministically;
- document deliberate eliminations;
- require equal unknown and residual counts;
- require one closure owner for every unknown;
- reject structurally empty rows and unused columns;
- require full structural rank.

DD-071 demonstrates both outcomes. Separate reboiler and sump states fail
because their connecting liquid flow lacks an equation. Combining their
explicit phase inventories inside one conserved bottom control volume removes
that internal transfer and passes the structural gate without adding a tuning
relation.

### 9.8 Numerical Residual And Jacobian Gate

Before any nonlinear solve:

- evaluate every registered residual directly with live properties;
- reject invalid reduced compositions without clipping or renormalization;
- require component and energy balances to telescope independently;
- publish physical variable and residual scales;
- require full numerical rank at the primary and bounded-perturbation guesses;
- repeat rank at two finite-difference step sizes;
- verify colored derivatives against an optional uncolored reference;
- reject zero unknown columns or dependencies outside the registry graph.

DD-072 passes this gate for the direct `281 x 281` C3/C4 system. The result
authorizes bounded continuation design, not a claim that a steady-state seed
has been solved or dynamically accepted.

### 9.9 Staged Continuation Gate

Each continuation stage must:

- contain equal active unknown and residual counts;
- replace only newly activated physical equations with smooth anchors;
- recover the exact direct physical residual at `lambda=1`;
- preserve valid composition, positive-variable, property, and conservation
  domains without clipping or projection;
- retain full numerical rank and condition estimate below the declared limit;
- meet its homotopy residual before accepting a point;
- stop at the declared minimum step and retry limit.

A full-rank stage can still fail because its fixed unreleased state does not
admit the requested physical endpoint. DD-073 demonstrates this distinction.
The five-stage implementation remains full rank and conservative, but Stage 1
cannot reconcile local DWSIM phase states exactly while ChemSep-derived
component inventory and internal energy remain fixed. The gate therefore
requires release-order redesign instead of tolerance relaxation or further
anchor tuning.

DD-074 applies the final redesign and demonstrates the complementary stop:
a stage can be square, conservative, and endpoint-exact while its physical
dependency graph is still structurally singular. The merged `240 x 240`
block has rank `239`; the live solve is therefore prohibited. Later stages
recover rank only after liquid hydraulics are added, but creating a new
hydraulics-first release sequence would violate the predefined hard stop.
Manual staged continuation is retired.

### 9.10 V2 Source-Equation Dynamic Gate

Before v2 may add energy or live property closure, its property-free source
assembly must reproduce an independent implementation dynamically, not only
pointwise.

The gate requires:

- nominal published-profile drift, without snapping to the source profile;
- an exactly scheduled `+1%` feed step;
- one deterministic bounded state perturbation;
- normalized full-trajectory parity `<1e-9`;
- a second-integrator or tighter-tolerance comparison `<1e-7`;
- differential and solver-integrated total/component conservation `<1e-10`;
- positive holdup and valid compositions without clipping or projection;
- product component withdrawal from current terminal compositions.

DD-079 passes this gate for three `500 min` trajectories. BDF/Radau
agreement is at most `1.60e-9`, and solver-integrated conservation is below
`2.77e-12`. Saved-grid trapezoidal quadrature is reported separately from the
differential and solver closure. Passing DD-079 completes Gate A and
authorizes only the one-volume Gate B energy/property study.

### Gate B: One-Volume Live Property And Energy Closure

Before assembling a reduced column, Gate B checks whether one inventory
volume can consistently own conserved component inventory and internal energy
while live thermodynamics reconstruct temperature and equilibrium vapor
composition.

DD-080 selects the mini8 feed volume by role, prescribes its pressure, and
rebuilds canonical internal energy from live DWSIM PR enthalpy and density.
It then checks five static states from three predefined guesses, numerical
rank at two finite-difference steps, live-density liquid height and derived
Francis flow, and four short conserved dynamics with both BDF and Radau.

DD-080 passes. Every `3 x 3` Jacobian is rank `3`, worst condition is below
`3`, worst algebraic residual is `5.43e-13`, worst BDF/Radau disagreement is
`3.75e-9`, and normalized component and energy conservation are below
`4.60e-16` and `2.01e-16`. No serialized enthalpy, vapor holdup, fixed tray
volume equality, clipping, projection, phase relaxation, or legacy governing
equation is used. Passing Gate B authorizes only the five-volume,
prescribed-pressure Gate C model.

### Gate C: Five-Volume Prescribed-Pressure Francis Column

Gate C asks whether the individually validated volume closures can be
assembled into one conservative column with a liquid reflux drum, three
interior hydraulic trays, a combined reboiler/sump, an inventory-free total
condenser, prescribed pressure, and prescribed section vapor rates.

DD-081 is the pre-solve portion of this gate. It reconstructs `NL/x` directly
from conserved inventories, evaluates all phase properties live with DWSIM
PR, checks exact inter-volume telescoping, and audits the scaled Jacobian at
two finite-difference steps for five declared states. The resulting direct
system is `38 x 38`; DD-077's `53 x 53` count retained 15 `NL/x`
reconstruction coordinates and identity rows that DD-081 eliminates exactly.

DD-081 passes with rank `38/38` in every numerical audit, worst condition
`1.19e6`, component telescoping below `4.0e-16`, and no zero row, zero column,
unregistered coupling, clipping, projection, fallback, or geometry
adjustment. The canonical residual is `0.511`, so the result does not claim a
steady solution. It authorizes one bounded DD-082 steady solve only.

## Where Gates Are Used In The Workflow

### During Initializer Development

1. Build a candidate seed.
2. Run local thermodynamic closure.
3. Run global hydraulic and terminal-equipment closure.
4. Stop if any algebraic gate fails.
5. Evaluate and solve steady component/energy residuals.
6. Run a short dynamic smoke test.
7. Apply dynamic gate.
8. If the dynamic gate fails, reject the candidate or inspect the model coupling defect.
9. If all applicable gates pass, serialize the accepted seed and verify restart/reload behavior.

Related docs:

- `docs/initializer_requirements_and_acceptance.md`
- `docs/initializer_how_to_guide.md`
- `docs/dynamic_column_initialization_strategy.md`

### During Dynamic Model Development

1. Run a baseline and candidate recipe.
2. Compare dynamic score, pressure behavior, boundary inventories, K drift, and liquid inventory.
3. Use audits to determine which block is unhealthy.
4. Change equations or runtime handoff only when a gate points to a concrete failure mode.
5. Re-run the same gates after the fix.

Current examples:

- feed flash K=1 gate/fix,
- product draw composition consistency,
- liquid hydraulic flow ownership,
- K-state drift monitoring.

### During Validation

1. Confirm the case topology and assumptions.
2. Confirm the model is not passing only because physics were disabled.
3. Apply dynamic health gates.
4. Apply the physical-closure gate.
5. Apply source-comparison or validation-specific metrics.
6. Only then claim validation.

## What A Gate Should Report

A useful gate should report:

- pass/fail,
- threshold used,
- measured value,
- time of worst value,
- final-window trend when the signal is time-dependent,
- worst state/stage/component where applicable,
- reason for failure,
- whether the result is absolute or baseline-relative.

For example, "failed" is less useful than:

```text
failed dynamic gate:
final steady_state_score = 1.54, threshold = 1.0
final-third score trend = worsening
worst state = tray_L, stage = 10, component = n-Propane
```

## What A Gate Should Not Do

A gate should not hide model behavior or force a result to pass.

Avoid using gates to:

- suppress a physical residual without understanding it,
- declare success from one metric while ignoring other known failures,
- tune around a single tray or component in non-generic model code,
- replace a model equation with an acceptance rule.

The gate should expose the decision. It should not become a quiet workaround.

## Current Practical Rule

For this project, a run should not be called clean, usable, or validated unless it satisfies the relevant gates for its purpose.

For an initializer candidate, that means at minimum:

- local thermodynamic closure passes,
- global hydraulic closure passes,
- terminal-equipment mapping is complete,
- no accepted projection or binding imported-profile/previous-step limiter owns the result,
- initial-guess robustness passes,
- residual gate passes or is clearly acceptable,
- dynamic smoke gate passes,
- dynamic score is stable or improving over the final window,
- K-state drift gate is acceptable,
- internal liquid inventory gate is acceptable,
- physical ownership is appropriate for the claimed use; rigorous claims require the physical-closure gate,
- restart/reload gate passes if the artifact is meant to be reused.

For a dynamic model development run, a failed gate is still useful. It tells us where the model or handoff strategy is still internally inconsistent.

Passing the rate, controller, and conservation gates permits the label **operational baseline**. It does not by itself permit **rigorous physical validation**. That stronger label also requires the physical-closure gate.
