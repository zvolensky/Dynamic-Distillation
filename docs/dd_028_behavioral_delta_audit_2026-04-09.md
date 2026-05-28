# DD-028 Behavioral Delta Audit (2026-04-09)

## Purpose

Compare the current `refactor/compute-efficiency` working tree against the
pre-refactor baseline on this branch to identify behavior-changing code deltas
that could explain `DD-022`.

Audit baseline:

- Git baseline: `e02932d` (`HEAD`)
- Compared target: current working tree

This audit is focused on behavior, not runtime speed.

## Scope

Reviewed deltas in:

- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- `src/dynamic_distillation/column_rhs_v1.py`

Focused on:

- top-end pressure / condenser / reflux-drum behavior
- bottom-end sump / reboiler / bottoms behavior
- controller feasibility logic
- runtime liquid-hydraulic override semantics
- startup / cadence paths only insofar as they could still affect the active
  validation runs

## What This Audit Rules Out

The current ugly validation case is not being driven by some of the newer
runtime-efficiency features, because the failing run family is using:

- `--thermo-every 1`
- no `--fast-startup`
- no startup-seed cache path

So the following are lower-probability causes for the active `DD-022` behavior:

- thermo cadence
- startup seed cache loading
- startup packet reuse thresholds

Those changes may affect startup behavior, but they are not the leading suspects
for the current long-horizon controller/hydraulic mismatch.

## High-Suspicion Behavioral Deltas

### 1. Coupled Pressure-Duty Now Has Real Condenser Mass-Split Authority

This is the single most important semantic delta found in the audit.

Current working tree adds:

- `condenser_duty_partial_condense_if_limited`
- new condenser bubble-state reuse
- new behavior where a total-condenser case can still allow duty-limited vapor
  slip to the top drum during coupled `pressure-control-mv=condenser-duty`
  operation

In `HEAD`, a total condenser in the RHS remained materially simpler:

- if pressure control used `condenser-duty` and coupling was not explicitly
  allowed, the runner auto-switched to `top-anchor`
- if coupling was allowed, the old condenser path still did not include the new
  partial-condense mass-split semantics now present in the working tree

Why this matters:

- it changes the top-end mass split, not just the thermo cost
- it changes how condenser duty affects `V_condensed_in`, `V_to_top_drum`,
  reflux-drum accumulation, and therefore pressure/inventory interaction
- it is strongly consistent with the new family of runs that moved from
  top-starvation to top overfill / pressure overshoot

Assessment:

- very likely contributor to `DD-022`

### 2. Liquid Hydraulic Override Semantics Have Changed Repeatedly

The old baseline used a scalar hydraulic blend:

- `liquid_hydraulic_override_alpha`

The working tree now includes:

- tray-local guarded override arrays
- residual-based backoff logic in the runner
- per-stage `liquid_hydraulic_override_alpha_per_stage`

This area already produced one confirmed bad behavior during the session:

- a global residual guard drove the whole lower section back toward the ChemSep
  profile
- that was not the intended meaning of the ChemSep data
- it has since been corrected to tray-local behavior

Why this matters:

- it directly changes internal liquid downflow on stages 2..N-1
- it can materially distort inventory transport and tray dryout behavior
- it is consistent with the observed `L_out_used` vs `L_out_hyd` mismatch in
  stages 12-18

Assessment:

- confirmed behavior-affecting refactor-area change
- still a leading suspect for remaining lower-section problems

### 3. True-Level Reflux Feasibility Logic Changed

The working tree adds `_desired_inventory_recovery_rate_lbmolph(...)` and uses
it to limit reflux demand from the distillate composition controller.

This was a real bug fix:

- the prior true-level path mixed `lbmol` and level fraction
- the cap was therefore not unit-consistent

But it is still behavior-changing, and the audit conclusion is:

- the old run family was partially being "helped" by the broken cap
- once fixed, the top-end coupling issue became more visible

Assessment:

- real semantic change
- likely not the root cause by itself
- did expose deeper top-end imbalance

### 4. Low-Holdup Energy / Equilibrium Guardrails Are New

The working tree adds:

- `_limit_equilibrium_phase_transfer_rates(...)`
- `_stabilize_low_holdup_temperature_rate(...)`

These were added in response to the catastrophic stage 11-13 blow-up and are
clearly stabilizing guards, not parity features.

Why this matters:

- they are intentionally behavior-changing
- they can keep the model finite while underlying transport/controller problems
  remain

Assessment:

- not the likely origin of `DD-022`
- but they do mean the current model is no longer behavior-identical to the old
  path in near-dry regimes

## Lower-Suspicion or Already-Existing Semantics

### 1. Pressure-Control Auto-Switch Was Already in Baseline

The baseline already had the behavior:

- `pressure-control-mv=condenser-duty`
- `condenser-duty-mode=total-condense`
- auto-switch to `top-anchor` unless `--allow-coupled-pressure-duty`

So that piece is not a new regression by itself.

### 2. Top-Drum Pressure State Was Already a Meaningful Part of the Hydraulic Path

The baseline already had:

- explicit top-drum pressure state
- pressure gating on stage-2 to drum vapor slip
- optional use of top-drum pressure as hydraulic anchor

So the existence of drum-pressure coupling is not itself new. The key new risk
is the changed condenser mass-split semantics under that coupled mode.

### 3. Explicit Sump-Fed Reboiler Path Was Already Present in the Baseline

The baseline already included:

- `reboiler_feed_from_sump`
- explicit bottom holdup participation in the reboiler/sump coupling

So the mere fact that the bottoms draw comes from the sump is not new.

That said, the active `DD-023` pathology still indicates this region is not
behaving credibly.

## Overall Interpretation

The audit does **not** point to a single accidental typo-level regression.

It points to a narrower but still important conclusion:

1. The current `DD-022` behavior is **not** primarily coming from cadence or
   startup-speed changes.
2. The most suspicious semantic drift is at the **top end**, where coupled
   pressure-duty now has materially different condenser mass-split behavior than
   the pre-refactor baseline.
3. The second major suspect is the **internal liquid hydraulic override
   machinery**, which changed meaning during the refactor and has already
   produced one confirmed unintended fallback pattern.
4. The newer low-holdup guardrails are stabilizers, not parity logic. They are
   helping avoid blow-up, but they also make the current runtime less directly
   comparable to the baseline in bad regimes.

## Recommended A/B Isolation Order

### A/B 1. Freeze Condenser Behavior Closer to Baseline

Keep the rest of the current code, but disable the new
`condenser_duty_partial_condense_if_limited` path for the coupled pressure-duty
validation case.

Goal:

- determine whether the ugly top-end behavior is primarily caused by the new
  duty-limited partial-condense semantics

### A/B 2. Hold Liquid Hydraulic Override Simple

Run with:

- explicit liquid hydraulics enabled
- fixed scalar override alpha
- no residual-driven tray-local backoff

Goal:

- determine whether current lower-section behavior is coming from the hydraulic
  closure itself or from the newer override/reconciliation guard logic

### A/B 3. Only After Semantics Are Frozen, Compare Backends

Once top-end and liquid-hydraulic semantics are frozen, compare:

- old behavior path + DWSIM
- frozen current behavior path + Clapeyron

Goal:

- separate backend differences from model-logic differences

## Verdict

The comparison audit yielded something useful:

- yes, there are real refactor-era semantic changes that can plausibly explain
  the new bad behavior
- the strongest suspects are **not** the thermo refactor broadly
- they are the **new coupled condenser mass-split behavior** and the **changed
  liquid-hydraulic override semantics**

That gives `DD-022` a much clearer next step than "keep patching symptoms."
