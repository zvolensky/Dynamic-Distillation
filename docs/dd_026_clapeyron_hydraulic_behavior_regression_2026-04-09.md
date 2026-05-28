# DD-026 Clapeyron Hydraulic Behavior Regression

Date: 2026-04-09

## Scope

This note tracks the behavior regression seen while pursuing the April 2026
compute-efficiency refactor on the depropanizer hydraulic path with
`thermo=clapeyron`, coupled condenser-duty pressure control, and true-level
controllers.

This is intentionally separate from the runtime-efficiency issue in
[issue_log.md](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/issue_log.md),
especially `DD-021`.

## Why This Is A Trackable Issue

The refactor produced a major wall-clock improvement, but the same branch also
surfaced behavior that is not yet acceptable for production-like runs:

- late-run mid-column instability or severe operating-point drift
- poor top-pressure tracking under coupled condenser-duty pressure control
- distillate composition drifting far above its SP
- bottom level saturating high for long periods
- very large internal liquid traffic in stages 12-14 during explicit
  liquid-hydraulic runs

The issue is now specific enough to track independently.

## Key Evidence

### 1. Initial behavior-first Clapeyron run blew up

Run: `20260408_183315`

Artifacts:
- [column_summary_20260408_183315.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_5min_behavior_20260408/column_summary_20260408_183315.csv)
- [column_profile_20260408_183315.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_5min_behavior_20260408/column_profile_20260408_183315.csv)

Observed:
- stages 11-13 reached absurd temperatures
- SS score ran away to about `8.15e7`
- failure centered on near-dry trays with tiny effective thermal mass

### 2. Low-holdup temperature and equilibrium guardrails removed the catastrophic blow-up

Run: `20260409_081358`

Artifacts:
- [column_summary_20260409_081358.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_1680s_truelevel_guarded_20260409/column_summary_20260409_081358.csv)
- [column_profile_20260409_081358.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_1680s_truelevel_guarded_20260409/column_profile_20260409_081358.csv)

Observed:
- run stayed finite through `1680 s`
- SS score improved from catastrophic to about `540`
- behavior still wrong: top pressure low, bottoms level pegged high, xD far above SP

### 3. A real runtime-mode regression was introduced during investigation

During the April 9 work, `runtime-mode=hydraulic` was briefly changed to default
internal liquid hydraulics on. That was not the documented pre-existing
behavior, and it materially worsened the true-level coupled-pressure runs.

This semantic drift has now been corrected in
[dynamic_run_scaffold_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/dynamic_run_scaffold_v1.py).

### 4. Explicit liquid-hydraulic runs still drift even after stabilization work

Runs:
- `20260409_085920`
- `20260409_091412`
- `20260409_095055`
- `20260409_181442`

Artifacts:
- [column_summary_20260409_085920.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_1680s_truelevel_liqhyd_guarded2_20260409/column_summary_20260409_085920.csv)
- [column_summary_20260409_091412.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_1680s_truelevel_liqhyd_guarded3_20260409/column_summary_20260409_091412.csv)

Observed:
- no catastrophic thermal detonation
- stronger residual-based liquid-hydraulic guarding materially improved the run
- final guarded explicit-liquid-hydraulic case still ended far from target:
  - `P_top_drum ≈ 228.9 psia`
  - `xD_comp_pv ≈ 0.5416` at SP `0.11`
  - bottom level remained saturated high
  - SS score still about `414.6`

### 5. Later coupling/local-guard work removed the blow-up but not the operating-point failure

Runs:
- `20260409_095055`
- `20260409_181442`

Artifacts:
- [column_summary_20260409_095055.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_600s_truelevel_liqhyd_coupledfix_20260409/column_summary_20260409_095055.csv)
- [column_profile_20260409_095055.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_600s_truelevel_liqhyd_coupledfix_20260409/column_profile_20260409_095055.csv)
- [column_summary_20260409_181442.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_8000s_truelevel_liqhyd_localguard_20260409/column_summary_20260409_181442.csv)
- [column_profile_20260409_181442.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_8000s_truelevel_liqhyd_localguard_20260409/column_profile_20260409_181442.csv)

Observed:
- the corrected `600 s` case stayed finite with much better pressure control (`P_top≈218.3 psia`)
- the `8000 s` verification run completed the full horizon at about `7.1 sim-s / wall-s`
- pressure control became excellent (`P_top≈220.45 psia`, `P_bot≈232.04 psia`)
- the operating point remained wrong:
  - distillate flow collapsed to `0`
  - bottoms draw saturated near `11905 lbmol/h`
  - top level drained low (`~0.239` at SP `0.5`)
  - bottom level saturated high (`1.0` at SP `0.5`)
  - `xD_comp_pv≈0.616` at SP `0.11`

This means the issue is no longer “the run blows up before we can inspect it.”
It is now “the run survives and is fast, but still settles into the wrong
inventory/separation regime.”

## Current Interpretation

This does not look like a single remaining typo or one-off CLI mistake.

Current best interpretation:

1. A genuine fragility existed in the low-holdup tray energy/equilibrium path.
   That part was real and has been improved.
2. A separate runtime-mode regression briefly made hydraulic behavior worse by
   forcing liquid hydraulics on by default. That has been corrected.
3. The remaining mismatch is a coupled-behavior problem in the
   Clapeyron + hydraulic + condenser-duty-pressure + true-level-control regime,
   especially when explicit liquid hydraulics are active.
4. The later local-guard/coupling fixes show that pressure tracking can be made
   credible without numerical failure, but the inventory/product split can still
   drift into a very wrong operating point.

## Code Changes Already Landed For This Issue

- low-holdup equilibrium phase-transfer limiting in
  [column_rhs_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/column_rhs_v1.py)
- low-holdup tray temperature-rate stabilization in
  [column_rhs_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/column_rhs_v1.py)
- restoration of documented hydraulic-mode liquid-hydraulics default in
  [dynamic_run_scaffold_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/dynamic_run_scaffold_v1.py)
- residual-based liquid-hydraulic backoff logic for explicit
  liquid-hydraulic runs in
  [dynamic_run_scaffold_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/dynamic_run_scaffold_v1.py)

## Remaining Next Actions

1. Isolate the coupled pressure-duty path from the explicit liquid-hydraulic path
   with smaller A/B runs.
2. Inspect bottoms-level saturation and its interaction with the lower-section
   hydraulic closure.
3. Inspect why stages 12-14 still sustain very large internal liquid rates in
   the explicit liquid-hydraulic regime even after residual-based backoff.
4. Inspect why the stabilized long run drains the top and fills the bottom even
   while pressure remains on target.
5. Keep this issue tracked separately from `DD-021`, which remains the main
   runtime-efficiency issue, and from `DD-023`, which now tracks the explicit
   sump/product composition pathology.

## Comparison Audit Update

A direct code audit against branch baseline `e02932d` was completed on
2026-04-09 and is captured in
[dd_028_behavioral_delta_audit_2026-04-09.md](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/dd_028_behavioral_delta_audit_2026-04-09.md).

That audit narrows the highest-risk behavior deltas to:

1. the newer coupled condenser-duty partial-condense path, which materially
   changes top-end mass-split semantics under pressure-duty coupling
2. the changed liquid-hydraulic override/backoff semantics, which materially
   affect lower-section liquid traffic

The audit also rules out startup-seed/cadence features as primary suspects for
the active behavior-validation case, because the failing validation runs were
already using `thermo_every=1` without fast-startup or startup-seed loading.

## 2026-04-10 A/B: Baseline Strict Total-Condense Split

To isolate the top-end semantic delta, a new `600 s` validation rerun was made
with the same coupled true-level explicit-liquid-hydraulics case but with the
new coupled total-condenser partial-condense behavior disabled, forcing the
older strict total-condense material split:

- run folder:
  [depropanizer_20stage_hydraulic_clapeyron_pr_600s_truelevel_liqhyd_topsplit_ab_baseline_detached_20260410](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_600s_truelevel_liqhyd_topsplit_ab_baseline_detached_20260410)
- summary:
  [column_summary_20260410_082910.csv](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_600s_truelevel_liqhyd_topsplit_ab_baseline_detached_20260410/column_summary_20260410_082910.csv)
- metadata:
  [run_metadata_20260410_082910.json](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_600s_truelevel_liqhyd_topsplit_ab_baseline_detached_20260410/run_metadata_20260410_082910.json)

Compared to the uglier `20260409_201751` run, behavior improved materially:

- `steady_state_score`: `920.46 -> 49.19`
- `P_top_psia`: `240.53 -> 228.54`
- `Top_level_ctrl_pv`: `0.6211 -> 0.5353`
- `Bottom_level_ctrl_pv`: `0.4542 -> 0.4859`
- `xD_comp_pv`: `0.2977 -> 0.1227`
- `Bottoms_stage_sump_tv_distance`: `0.2221 -> 0.0651`
- `ss_max_temp_rate_F_per_s`: `138.07 -> 7.38`

This does **not** fully close `DD-022`, because the run still did not converge
cleanly (`steady_state_flag=0`, `P_top≈228.5 psia`, `xD≈0.1227` at SP `0.11`).
But it is strong evidence that the newer coupled partial-condense mass-split
semantics were a major contributor to the bad top-end behavior.
