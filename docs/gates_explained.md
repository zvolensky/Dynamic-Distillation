# Gates Explained

## Purpose

A gate is an explicit pass/fail or proceed/hold decision based on measured model behavior.

In this project, gates are needed because a dynamic distillation run can look acceptable by one metric while still being physically or numerically unhealthy by another. For example:

- a seed can reduce static residuals but blow up dynamically,
- a run can pass a rate-based steady-state score while an internal liquid inventory is slowly draining,
- a run can look quiet while `K_state` drifts away from live thermo `K_thermo`,
- a startup sequence can become unstable if liquid or vapor hydraulics are turned on too abruptly.

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
- related fields identifying the worst state, stage, and component.

Primary implementation:

- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Typical use:

- decide whether the run is dynamically quiet over the current window,
- compare run recipes,
- provide a compact health indicator in logs.

Important limitation:

- this is mostly a rate gate. It can miss level or consistency problems such as slow K-state drift or slow liquid inventory depletion. That is why additional gates now exist.

### 4. K-State Drift Gate

The K-state gate checks whether the integrated composition state remains consistent with thermo equilibrium.

It asks whether:

- `K_state = y/x` remains close to live thermo `K_thermo`,
- the mismatch is growing,
- the final mismatch is physically meaningful.

Primary tool:

- `tools/audit_k_state_drift.py`

Typical use:

- reject a run that looks quiet by rate metrics but is drifting away from thermo consistency,
- distinguish a truly healthy dynamic run from a merely slow-moving inconsistent run.

This gate was added because a 900 s run could pass the rate-based score while `K_state` versus `K_thermo` remained materially inconsistent.

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

## Where Gates Are Used In The Workflow

### During Initializer Development

1. Build a candidate seed.
2. Run a residual audit.
3. If residual gate fails, diagnose and revise the candidate.
4. If residual gate passes or improves, run a short dynamic smoke test.
5. Apply dynamic gate.
6. If dynamic gate fails, reject the candidate or inspect the model coupling defect.
7. If both pass, serialize the accepted seed and verify restart/reload behavior.

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
4. Apply source-comparison or validation-specific metrics.
5. Only then claim validation.

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

- residual gate passes or is clearly acceptable,
- dynamic smoke gate passes,
- dynamic score is stable or improving over the final window,
- K-state drift gate is acceptable,
- internal liquid inventory gate is acceptable,
- restart/reload gate passes if the artifact is meant to be reused.

For a dynamic model development run, a failed gate is still useful. It tells us where the model or handoff strategy is still internally inconsistent.
