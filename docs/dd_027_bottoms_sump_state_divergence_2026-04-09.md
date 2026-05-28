# DD-027 Bottoms Sump State Divergence

Date: 2026-04-09

## Scope

This note tracks a narrower pathology discovered during the longer stabilized
Clapeyron hydraulic validation runs: the explicit bottoms sump state can drift
to a nonphysical composition that sharply diverges from the bottom tray liquid
state and from expected depropanizer behavior.

This is related to, but distinct from, the broader coupled-behavior issue
tracked in [dd_026_clapeyron_hydraulic_behavior_regression_2026-04-09.md](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/dd_026_clapeyron_hydraulic_behavior_regression_2026-04-09.md).

## Why This Is A Separate Issue

The broader run can now stay numerically stable and hold pressure close to
target. Even so, the explicit sump/product state itself can become obviously
wrong:

- the bottoms product is drawn from the sump, not from stage 20
- the sump composition can diverge sharply from the bottom tray composition
- when that happens, the bottoms KPI may be physically impossible even if the
  tray profile still looks mixed

That deserves separate tracking because it is no longer just a general
"operating-point drift" symptom. It is an explicit state-pathology at the sump.

## Key Evidence

### 1. Long stabilized run completed, but bottoms product became nonphysical

Run: `20260409_181442`

Artifacts:
- [column_summary_20260409_181442.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_8000s_truelevel_liqhyd_localguard_20260409/column_summary_20260409_181442.csv)
- [column_profile_20260409_181442.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_8000s_truelevel_liqhyd_localguard_20260409/column_profile_20260409_181442.csv)

Observed final values:
- bottoms flow `B ≈ 11904.95 lbmol/h`
- sump holdup `Bottoms_L_lbmol ≈ 2115.24`
- sump product composition:
  - `Bottoms_x_n_Propane = 1.0`
  - `Bottoms_x_n_Butane = 0.0`
  - `Bottoms_x_n_Pentane = 0.0`
- bottom tray liquid composition:
  - `x_Bottoms_n_Propane ≈ 0.1650`
  - `x_Bottoms_n_Butane ≈ 0.6335`
  - `x_Bottoms_n_Pentane ≈ 0.2014`

Those two states are not reconcilable as a believable depropanizer bottom end.

### 2. The mismatch is not just a reporting-label mistake

During investigation, the export semantics were rechecked:

- `Bottoms_x_*` means explicit sump composition
- `x_Bottoms_*` means bottom-stage liquid composition

That means the all-propane bottoms result reflects the actual explicit sump
state as stored/exported in the model at the end of the run. It is not merely a
column-summary labeling bug.

### 3. New mismatch diagnostics were added

To make this easier to track in future runs, the summary export now includes:

- `Bottoms_x_source`
- `Bottoms_stage_sump_tv_distance`
- `Bottoms_sump_x_*`

These let future reviews distinguish:
- the explicit bottoms/sump composition
- the stage-20 liquid composition
- the magnitude of their divergence

## Current Interpretation

Current best interpretation:

1. The stabilized local-guard path removed the catastrophic blow-up and allowed
   the run to survive long enough to expose this more subtle bottom-end
   pathology.
2. The explicit sump mass/composition update is drifting away from the tray
   state in a way that is not physically believable for this case.
3. The issue is likely tied to the same broader inventory/flow split mismatch
   seen in the coupled true-level hydraulic runs, but it is specific enough to
   merit separate tracking.

## Next Actions

1. Trace the explicit sump component mass balances over the late portion of the
   run.
2. Check whether boilup, bottoms draw, and tray-20-to-sump transfer are
   consistent with the explicit sump composition update.
3. Compare sump component-balance closure to stage-20 component-balance closure
   in the same time window.
4. Keep this issue linked to `DD-022`, but do not bury it inside the broader
   hydraulic behavior discussion.
