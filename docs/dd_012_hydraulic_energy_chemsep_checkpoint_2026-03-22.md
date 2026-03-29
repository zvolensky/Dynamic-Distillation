# DD-012 Hydraulic-Energy ChemSep Checkpoint

Date: 2026-03-22 (local)
Status: active diagnosis
Related notes:
- `docs/dd_011_hydraulic_parity_drift_report_2026-02-19.md`
- `docs/dd_011_hydraulic_parity_followup_2026-02-21.md`

Historical note (2026-03-28):
This checkpoint remains useful as a record of the March 22 hydraulic-energy diagnosis, but it no longer reflects the current best stabilized baseline. Since this note:
1. The stage-10 equilibrium-relaxation trigger was materially reduced by using live PR selectively in the eq-relax flash path.
2. The remaining late instability was traced to a tiny-capacitance stage-1 condenser temperature ODE under specified-duty operation.
3. The stage-1 condenser was converted to a condenser-transfer temperature closure, producing a stable `600 s` true-level hydraulic run (`20260328_145436`).

Use this document as historical diagnostic context, not as the current best-reference branch summary. For current status, use [issue_log.md](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/issue_log.md).

## Purpose

Capture the current state of the 20-stage ChemSep reconciliation effort after the March 22, 2026 hydraulic-energy fixes and diagnostic runs.

This note supersedes earlier assumptions that the main failure was startup corruption. Startup parity has now been materially repaired. The remaining problem is the long-horizon behavior of the hydraulic-pressure + energy-vapor closure itself.

## Executive Summary

Current status:
1. The 20-stage baseline workbook now loads the ChemSep seed correctly into the dynamic model.
2. `runtime-mode hydraulic` now starts at the correct product compositions instead of immediately overwriting them.
3. Hydraulic startup residuals were reduced from about `64.26 lbmol/h` to about `2.01 lbmol/h`.
4. The remaining failure is a real long-horizon instability in the hydraulic-energy dynamic closure that develops around `120-150 s`.
5. `bdf` and `radau` are not yet solving this case; both exceed RHS-evaluation caps and fall back to explicit Euler.
6. A misleading fallback-path bug was present and has now been fixed, so fallback runs no longer create a false sense of stability.

Bottom line:
1. Startup parity is no longer the main blocker.
2. The model now starts near ChemSep and stays near it briefly.
3. The real unresolved issue is the evolving hydraulic-energy dynamics after startup.

## March 23, 2026 Update

The case definition was later reconciled against the actual ChemSep warmer-feed workbook:
- `ChemSep Depropanizer_warmer_feed.xls`

This produced a corrected dynamic seed workbook:
- `sandbox/mini8/input/distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx`

Current best general-purpose hydraulic branch for this case:
1. `runtime-mode hydraulic`
2. `pressure_control_mV = condenser-duty`
3. `equilibrium_relaxation_mode = phase-holdup`
4. stripping-section phase-holdup softener enabled ("stripguard2")
5. top tray pressure anchored to live top-drum pressure when condenser-duty pressure control is active

Best short-horizon warmer-feed evidence so far:
- `logs/case20_hydraulic_120s_pcq_explicit_pool_phaseholdup_stripguard2_prtop_drumanchor_chemsep_warmer_seed_dmldiag_20260323/column_summary_20260323_161315.csv`

At `120 s`:
1. `P_top ~= 222.21 psia`
2. `P_bottom ~= 232.03 psia`
3. `xD(C4) ~= 0.09907`
4. `Q_cond ~= -50.291 MMBtu/h`

Interpretation:
1. Pressure behavior is now broadly credible.
2. The specified `2 psi` condenser drop is being honored (`P_stage2 - P_top_drum ~= 2 psi`).
3. The main remaining mismatch is lower-section liquid-holdup / hydraulic-diagnostic behavior, not top-pressure control.
4. `L_out_used` remains the trustworthy active liquid-flow profile; `L_out_hyd` is still a diagnostic signal unless liquid-hydraulic override is explicitly enabled.

## Workbook Seed Facts

Baseline workbook:
- `sandbox/mini8/input/distillation_column_template_20stage_baseline.xlsx`

Confirmed seed values:
1. Feed:
   - stage `12`
   - `T = 174.999 F`
   - `P = 232.06 psia`
   - vapor fraction `0`
   - `F = 7142.98 lbmol/h`
2. Distillate stream target from workbook:
   - `D = 2380.99 lbmol/h`
   - `xD(C4) = 0.0943265`
3. Bottoms stream target from workbook:
   - `B = 4761.98 lbmol/h`
   - `xB(C3) = 0.0471661`

These targets are already encoded in the workbook and are now preserved at startup.

## Code Fixes Implemented In This Checkpoint

### 1. Hydraulic preset no longer overwrites ChemSep seed behavior

File:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Changes:
1. `runtime-mode hydraulic` no longer silently enables internal liquid-hydraulic override unless explicitly requested.
2. `runtime-mode hydraulic` no longer silently enables vapor-holdup relaxation unless explicitly requested.
3. `runtime-mode hydraulic` now defaults feed re-flash at stage conditions off unless explicitly requested.

Rationale:
The ChemSep/Excel seed already reflects the intended steady-state internal profiles and feed effects. Reapplying startup helper logic was moving the model away from the target before the first meaningful step.

### 2. Energy vapor-flow solve now uses provider enthalpies

File:
- `src/dynamic_distillation/column_rhs_v1.py`

Change:
1. The `vapor_flow_model="energy"` closure now uses thermo-provider enthalpies in the vapor-flow solve when available, instead of falling back to simplified constant-Cp enthalpy calculations when no `HL_prev/HV_prev` cache is present.

Rationale:
This materially improved startup parity for the hydraulic-energy path.

### 3. Startup thermo conditioning preserves boundary product seeds

File:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Change:
1. Startup thermo conditioning now preserves seeded reflux-drum and bottoms-sump liquid compositions instead of replacing them with neighboring tray compositions.

Rationale:
Before this fix, the runner started with the correct workbook seed, then immediately overwrote:
- `xD(C4): 0.0943 -> ~0.1299`
- `xB(C3): 0.0472 -> ~0.0600`

That corruption is now gone.

### 4. Stiff-integrator fallback now uses the correct RHS

File:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Change:
1. When `bdf`/`radau` attempts fail and fall back to explicit Euler, the fallback explicit step now uses the live outer-step RHS instead of the frozen-thermo stiff-substep RHS.

Rationale:
Before this fix, fallback runs could look artificially calmer than true explicit runs, which made the long-horizon behavior misleading.

### 5. Regression coverage added

Files:
- `tests/test_column_rhs_v1.py`
- `tests/test_dynamic_run_scaffold_v1.py`

Focused results:
1. provider-enthalpy energy-vflow regression added and passing
2. hydraulic runtime-default regressions added and passing
3. startup boundary-composition preservation regression added and passing
4. stiff fallback separate-RHS regression added and passing

## Residual Audit Results

Audit tool:
- `tools/steady_state_residual_audit.py`

Key outputs:
- `logs/steady_state_residual_audit_baseline_parity_20260322.csv`
- `logs/steady_state_residual_audit_baseline_hydraulic_post_enthalpy_20260322.csv`
- `logs/steady_state_residual_audit_baseline_hydraulic_post_feedflash_20260322.csv`

Key progression:
1. Earlier hydraulic startup residual: about `64.2573 lbmol/h`
2. After provider-enthalpy fix: hydraulic default scenario down to about `5.6023 lbmol/h`
3. With hydraulic default feed-flash disabled: hydraulic default scenario down to about `2.0143 lbmol/h`

Interpretation:
The big startup mismatch is no longer caused by helper defaults. The remaining mismatch at `t=0` is much smaller and no longer invalidates the ChemSep seed.

## Key Dynamic Evidence

### A. One-step hydraulic check after boundary-seed fix

Artifacts:
- `logs/case20_hydraulic_one_step_post_boundaryfix_20260322/column_summary_20260322_124110.csv`

At `t=0`:
1. `xD(C4) = 0.094326539`
2. `xB(C3) = 0.047166055`

Interpretation:
The dynamic run now truly starts on the ChemSep seed.

### B. 30 s hydraulic open-loop run from ChemSep seed

Artifacts:
- `logs/case20_hydraulic_30s_post_parityfix_20260322/column_summary_20260322_124408.csv`

Trend:
1. `xD(C4): 0.0943265 -> 0.0953078`
2. `xB(C3): 0.0471661 -> 0.0472389`
3. `P_top: 218.44 -> 217.28 psia`

Interpretation:
Short-horizon behavior is now much more believable. The model no longer immediately peels away from ChemSep.

### C. 600 s hydraulic run from ChemSep seed

Artifacts:
- `logs/case20_hydraulic_600s_from_chemsep_20260322/column_summary_20260322_125057.csv`

Trend:
1. `0 s`: `xD(C4)=0.09433`, `xB(C3)=0.04717`
2. `60 s`: `xD(C4)=0.09675`, `xB(C3)=0.04739`
3. `120 s`: `xD(C4)=0.10033`, `xB(C3)=0.04820`
4. `180 s`: `xD(C4)=0.10481`, `xB(C3)=0.05068`, score blows up
5. `600 s`: `xD(C4)=0.20620`, `xB(C3)=0.06749`, `score=577.94`

Interpretation:
The real long-horizon instability remains.

## Fixed-Duty Integrator Comparison

All runs below used:
1. 20-stage baseline workbook
2. `runtime-mode hydraulic`
3. `condenser-duty-mode specified`
4. `Q_cond = -49.8304 MMBtu/h`
5. thermo pooling:
   - `--thermo table-pool`
   - `--thermo-pool-workers 12`
   - `--thermo-pool-chunk-size 4`

### 1. Explicit Euler, fixed duty, 240 s

Artifacts:
- `logs/case20_hydraulic_240s_fixq_explicit_pool_20260322/column_summary_20260322_141708.csv`

Final:
1. `P_top = 239.55 psia`
2. `xD(C4) = 0.10623`
3. `xB(C3) = 0.04778`
4. `steady_state_score = 224.21`

Behavior:
Destabilizes around `120-150 s`.

### 2. BDF requested, fixed duty, 240 s, before fallback fix

Artifacts:
- `logs/case20_hydraulic_240s_fixq_bdf_pool_20260322/column_summary_20260322_143053.csv`

Observed:
1. fell back to explicit on every step
2. nevertheless appeared much calmer
3. held `P_top` at spec while composition drifted badly

Interpretation:
This was misleading.

### 3. BDF requested, fixed duty, 240 s, after fallback fix

Artifacts:
- `logs/case20_hydraulic_240s_fixq_bdf_pool_post_fallbackfix_20260322/column_summary_20260322_150528.csv`

Final:
1. `P_top = 239.55 psia`
2. `xD(C4) = 0.10623`
3. `xB(C3) = 0.04778`
4. `steady_state_score = 224.21`
5. `integrator_used_mode = explicit-euler`
6. `integrator_fallback_used = 1`

Interpretation:
After the fallback bug fix, BDF-requested behavior matches the plain explicit run. This is the correct and trustworthy outcome.

### 4. Radau requested, fixed duty, 240 s

Artifacts:
- `logs/case20_hydraulic_240s_fixq_radau_pool_20260322/column_summary_20260322_151922.csv`

Observed:
1. exceeded RHS cap on every step
2. fell back to explicit on every step
3. followed the same unstable trajectory as explicit/BDF-fallback

Interpretation:
`radau` is not currently rescuing the hydraulic-energy case either.

## What Has Been Ruled Out

These are no longer the main explanation:
1. wrong feed temperature
2. missing ChemSep product targets in the workbook
3. startup seed corruption from top/bottom product composition overwrite
4. hidden liquid-hydraulics startup override
5. hidden vapor-holdup relaxation startup override
6. misleading fallback-path stability from frozen-thermo explicit fallback

## Current Best Problem Statement

The 20-stage hydraulic-energy model now starts correctly from the ChemSep seed, but the coupled hydraulic-pressure + energy-vapor dynamic closure develops a real instability around `120-150 s`, causing top pressure and distillate purity to drift away from the ChemSep operating point.

## Current Hypotheses

Priority hypotheses:
1. The hydraulic-energy closure becomes too stiff and/or non-smooth in the `120-150 s` window.
2. Vapor-flow or hydraulic limiting behavior is introducing solver-hostile non-smoothness.
3. State scaling is still poor for implicit Newton work, so `bdf`/`radau` cannot converge before hitting RHS limits.
4. The upper-column pressure/vapor/energy coupling remains excessively sensitive in this pressure range.

What is not yet proven:
1. index-2 DAE failure as the primary diagnosis
2. missing vapor-holdup physics
3. controller-induced instability as the primary cause

## Recommended Next Experiments

1. Run `ida` on the same fixed-duty `240 s` case with thermo pooling.
2. Add diagnostics for vapor-flow clamp activation in the `120-150 s` window.
3. Inspect state scaling and residual weighting, especially for energy states.
4. Inspect Jacobian conditioning / algebraic residual behavior near onset.
5. Avoid more long blind runs until the `120-150 s` onset is better understood.

## Practical Status

Satisfied:
1. startup parity for ChemSep seed
2. trustworthy interpretation of explicit vs stiff-fallback behavior
3. thermo pooling deployment for longer diagnostic runs

Not satisfied:
1. long-horizon stability of `runtime-mode hydraulic`
2. implicit integration viability for the hydraulic-energy case
3. parity-grade confidence beyond the short-horizon regime

## Later Same-Day Update

Two more targeted experiments materially narrowed the issue.

### 5. Startup hydraulic-energy consistency pass

Code:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

New capability:
1. added opt-in startup hydraulic-energy consistency relaxation
2. uses the existing pilot algebraic solve at `t=0`
3. takes bounded pseudo-time startup steps only when a normalized startup objective improves

Experiment:
- `logs/case20_hydraulic_180s_fixq_explicit_pool_startuphe_20260322/column_summary_20260322_172255.csv`

Observed:
1. startup objective changed only slightly: about `9.67 -> 9.54`
2. long-horizon trajectory at `180 s` was essentially unchanged from the baseline fixed-duty explicit run
3. final `xD(C4) ~= 0.1010`, `P_top ~= 230.83 psia`, `steady_state_score ~= 231`

Interpretation:
The first consistent-startup pass did not fix the real instability. It is available as a diagnostic tool, but it is not the breakthrough lever.

### 6. Vapor-flow clamp diagnostics

Code:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

New logging:
1. `vflow_energy_clamped`
2. `vflow_energy_limit_hi_lbmolph`
3. `vflow_energy_limit_lo_lbmolph`

Experiment:
- `logs/case20_hydraulic_150s_fixq_explicit_pool_vflowdiag_20260322/column_profile_20260322_173231.csv`
- `logs/case20_hydraulic_150s_fixq_explicit_pool_vflowdiag_20260322/column_summary_20260322_173231.csv`

Observed:
1. no vapor-flow clamps were active at `120 s`, `135 s`, or `150 s`
2. all active stages had `vflow_energy_ok = 1`
3. the failure still appeared around `150 s`
4. the strongest growing mismatch was not a flow clamp but `K_state / K_thermo`, especially pentane on stages `2-4`

Interpretation:
The `120-150 s` failure is not being caused by the vapor-flow hard clamps or denominator collapse.

### 7. Hydraulic run with `equilibrium-relaxation-mode phase-holdup`

Experiment:
- `logs/case20_hydraulic_150s_fixq_explicit_pool_phaseholdup_20260322/column_summary_20260322_174218.csv`
- `logs/case20_hydraulic_240s_fixq_explicit_pool_phaseholdup_20260322/column_summary_20260322_175144.csv`

Comparison to old hydraulic default:
1. old hydraulic default was `equilibrium-relaxation-mode=composition-only`
2. that path blew up by `150 s` with score about `209`
3. the `phase-holdup` run stayed calm through `150 s` with score about `3.17`
4. the `phase-holdup` run stayed calm through `240 s` with score about `3.05`

Key `240 s` result:
1. `P_top ~= 229.98 psia`
2. `xD(C4) ~= 0.10479`
3. `xB(C3) ~= 0.05277`
4. `ss_max_rel_state_rate_per_s ~= 0.00915`
5. `ss_max_temp_rate_F_per_s ~= 0.0285`
6. `K_state_over_K_thermo_max_abs ~= 1.88`

Interpretation:
This is the first experiment that materially stabilizes the hydraulic-energy long-horizon path. The main failure driver now looks less like startup inconsistency or vapor-flow clamp pathology, and more like the `composition-only` equilibrium-relaxation choice allowing `K_state = y/x` to drift too far from thermo equilibrium.

## Updated Best Hypothesis

The dominant destabilizing choice in the hydraulic-energy path appears to be `equilibrium-relaxation-mode=composition-only`. Switching to `phase-holdup` materially reduces `K_state / K_thermo` drift in the upper section and prevents the previous `150-240 s` blow-up under the same fixed-duty conditions.

## Updated Next Experiments

1. Extend the `phase-holdup` hydraulic fixed-duty run to `600 s`.
2. Compare the `600 s` `phase-holdup` result directly to the earlier `composition-only` `600 s` failure case.
3. If the `600 s` behavior holds, consider changing the hydraulic default equilibrium-relaxation mode or adding a hydraulic-specific recommendation in the CLI/docs before making it the default.

## Evening Update

Three more experiments changed the picture again.

### 8. `600 s` hydraulic fixed-duty run with `phase-holdup`

Experiment:
- `logs/case20_hydraulic_600s_fixq_explicit_pool_phaseholdup_20260322/column_summary_20260322_185104.csv`

Observed:
1. the run did not blow up
2. final `xD(C4) ~= 0.12322` versus the old `composition-only` failure at `~0.20620`
3. final `steady_state_score ~= 1.41`
4. final `K_state_over_K_thermo_max_abs ~= 2.70`

Interpretation:
`phase-holdup` is a real long-horizon stabilization lever for hydraulic+energy. It does not recover ChemSep purity, but it turns the previous catastrophic drift into a controlled, slowly evolving trajectory.

### 9. Pressure-profile realism problem in the stabilized branch

Observed from the `600 s` `phase-holdup` profile:
1. tray pressures became nearly flat at about `240 psia`
2. this is not physically acceptable for the 20-stage case

Interpretation:
The old anchored hydraulic pressure treatment was hiding the true internal tray-to-tray profile. The run was more stable, but the internal pressure distribution was not believable.

### 10. Open-loop free-pressure hydraulic branch

Code:
- `src/dynamic_distillation/column_rhs_v1.py`

Change:
1. when hydraulic runs have no explicit top anchor, use the free hydraulic tray profile instead of scaling all tray drops to the distillate-drum pressure
2. keep generic tray-to-drum continuity disabled by default in open-loop mode so the raw tray pressure profile is visible

Pressure-diagnostic verification:
- `logs/case20_hydraulic_onestep_fixq_phaseholdup_freep_postdpfix_20260322/column_profile_20260322_200203.csv`

Observed at `t=0`:
1. stage `1` pressure `~= 228.43 psia`
2. stage `19-20` pressure `~= 232.06 psia`
3. raw internal tray drops are small but nonzero, mostly about `0.07 psi/stage` with the explicit `2 psi` condenser drop at stage `2`

Key free-pressure dynamic runs:
- `logs/case20_hydraulic_150s_fixq_explicit_pool_phaseholdup_freep_20260322/column_summary_20260322_194033.csv`
- `logs/case20_hydraulic_240s_fixq_explicit_pool_phaseholdup_freep_postdiag_20260322/column_summary_20260322_195053.csv`

Key `240 s` free-pressure result:
1. final `P_top ~= 230.40 psia`
2. final `xD(C4) ~= 0.10223`
3. final `xB(C3) ~= 0.05266`
4. final `steady_state_score ~= 3.40`
5. final `K_state_over_K_thermo_max_abs ~= 1.84`
6. tray pressure profile remained graded rather than collapsing flat

Transient behavior:
1. there is still a sharp relative-rate burst around `120 s`
2. a smaller burst reappears around `225 s`
3. neither burst coincides with a vapor-flow clamp event
4. the run damps back down after each burst rather than diverging

Interpretation:
The free-pressure branch fixes the physically wrong flat tray-pressure profile and keeps the hydraulic run in a plausible pressure regime through `240 s`. It is somewhat rougher dynamically than the anchored `phase-holdup` branch, but it is materially more believable physically.

## Current Best Read

Two separate issues were interacting:

1. `composition-only` equilibrium relaxation was a major destabilizer.
2. automatic top-drum anchoring in open-loop hydraulic mode was hiding a physically wrong flat tray-pressure profile.

With `phase-holdup` plus free hydraulic tray pressure:
1. the run is much more stable than the original hydraulic baseline
2. the tray pressure profile is physically graded again
3. ChemSep parity is still not achieved, but the remaining gap now looks like a tractable model-reconciliation problem rather than a catastrophic runtime failure

## Current Next Experiments

1. diagnose the `120 s` and `225 s` relative-rate bursts in the free-pressure branch, especially which tray states dominate `ss_max_rel_state_rate_per_s`
2. decide whether open-loop hydraulic needs a mild tray-to-drum continuity treatment that does not reintroduce full top-anchor scaling
3. once the burst mechanism is understood, extend the free-pressure `phase-holdup` branch to `600 s` and re-evaluate ChemSep parity

## Late Evening Burst Diagnosis

Additional code:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

New diagnostic:
1. steady-state logs now record the dominant relative-rate inventory family
2. logs also record the stage and component index responsible for `ss_max_rel_state_rate_per_s`

Experiment:
- `logs/case20_hydraulic_240s_fixq_explicit_pool_phaseholdup_freep_burstdiag_20260322/column_summary_20260322_200759.csv`
- `logs/case20_hydraulic_240s_fixq_explicit_pool_phaseholdup_freep_burstdiag_20260322/column_profile_20260322_200759.csv`

Observed:
1. the burst driver is consistently `tray_V`, not tray liquid, drum, or sump inventory
2. the `90 s` burst is driven by stage `18`, component `2` (`n-Butane`) vapor inventory
3. the large `120 s` burst is driven by stage `14`, component `1` (`n-Propane`) vapor inventory
4. the `225 s` burst is driven by stage `11`, component `2` (`n-Butane`) vapor inventory

Most important local event:
1. at `120 s`, stage `14` total vapor holdup is only about `0.224 lbmol`
2. at that same time, stage `14` vapor composition for propane is exactly `0.0`
3. stage `14` still has large vapor traffic, `V_out ~= 7515 lbmol/h`
4. neighboring stages `13` and `15` have much larger vapor holdups and do not collapse the same way

Interpretation:
The major free-pressure burst is not a whole-column blow-up. It is a local vapor-holdup redistribution event. The steady-state metric becomes very large because one tray vapor component inventory becomes nearly empty, so even a modest finite-difference change in that tiny inventory produces a very large relative rate. This is most visible at stage `14` propane vapor at `120 s`.

Working hypothesis:
1. `phase-holdup` is stabilizing the overall hydraulic-energy path
2. but it may be over-relaxing local tray vapor inventories in the middle section under the free-pressure profile
3. the next fix should probably target local vapor-holdup regularization or the phase-holdup update on these near-empty trays, rather than pressure anchoring

## Phase-Holdup Guard Trial

Additional code:
- `src/dynamic_distillation/column_rhs_v1.py`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Change:
1. added a smooth `equilibrium_phase_holdup_guard_lbmol`
2. for hydraulic free-pressure runs using `phase-holdup`, near-empty vapor trays now blend toward current vapor inventory instead of collapsing abruptly to the flash target
3. default guard used for current hydraulic branch is `1.0 lbmol`

Verification:
- `tests/test_module8b_equilibrium_relaxation.py`
- `tests/test_dynamic_run_scaffold_v1.py`

Experiment:
- `logs/case20_hydraulic_240s_fixq_explicit_pool_phaseholdup_freep_guard1_20260322/column_summary_20260322_202734.csv`
- `logs/case20_hydraulic_240s_fixq_explicit_pool_phaseholdup_freep_guard1_20260322/column_profile_20260322_202734.csv`

Observed:
1. the dominant burst is still in `tray_V`, but the worst `120 s` spike drops from about `255.9` to about `135.4`
2. the stage `14` propane-vapor collapse no longer goes to zero; at `120 s`, stage `14` has:
   - `MV ~= 0.234 lbmol`
   - `y_propane ~= 0.548`
   - `K_state_over_K_thermo_n_Propane ~= 1.18`
3. the later `225 s` burst improves materially, from about `7.66` to about `2.66`
4. final `240 s` parity remains similar:
   - `P_top ~= 230.79 psia`
   - `xD(C4) ~= 0.10269`
   - `xB(C3) ~= 0.05339`
   - `steady_state_score ~= 3.55`

Interpretation:
The guard fixes the specific local vapor-component collapse mechanism we identified. It does not eliminate all transient relative-rate bursts, but it turns the worst event into a milder local redistribution while keeping the physically graded pressure profile intact.
