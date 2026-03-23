# Huang Hybrid Main Model

This note records the main-model application of the Huang-inspired hybrid path.

## What is now applied

- The runner has a named runtime mode: `--runtime-mode huang`.
- In this mode, the repo intentionally uses a partitioned structure:
  - `pressure_model = hydraulic`
  - `vapor_flow_model = profile`
  - `liquid_hydraulic_model = huang-htc`
  - internal liquid-hydraulic override enabled
- The liquid `huang-htc` closure computes internal tray liquid downflow from:
  - `L_out ~= ML_tray / tau_htc`

## Why this path

- Huang's GRU work is a practical bridge between purely sequential profile-based dynamics and a fully simultaneous equation-oriented DAE build.
- The current repo already contains a partitioned pressure update and vapor-holdup relaxation path.
- The simultaneous dense Newton prototype was informative, but too expensive to be a practical development path.

## What this is not

- This is not a full reproduction of Huang's published architecture.
- The vapor flow is still profile-based in `runtime-mode huang`, not solved by a new implicit simultaneous pressure/flow system.
- The tray liquid model is HTC-based, not a full active-area/downcomer split.

## Intended use

- Use `runtime-mode huang` as the explicit Huang-inspired bridge path when testing reduced-risk pressure/liquid coupling changes.
- Do not treat `runtime-mode hydraulic` and `runtime-mode huang` as interchangeable:
  - `hydraulic` is the tighter pressure/energy-coupled development path
  - `huang` is the more weakly partitioned Huang-style hybrid path

## Next Huang-side work if continued

- Pressure-side tuning and validation in the main runner
- A/B comparisons of `hydraulic` vs `huang` on the same cases
- Decide whether the Huang bridge is stable enough to use for operating-point verification before any larger equation-oriented rebuild

## First short main-run comparison

Command pattern used on March 20, 2026:

- `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel sandbox\mini8\input\distillation_column_template_8stage.xlsx --thermo table --thermo-table cache\thermo_table.json --include-energy --condenser-duty-mode specified --condenser-duty-btuph -49640000 --n-steps 20 --dt 0.2 --log-every 20 --runtime-mode <mode>`

Artifacts:

- Huang:
  - `logs/mini8_huang_short_20260320/column_profile_20260320_151416.csv`
  - `logs/mini8_huang_short_20260320/column_summary_20260320_151416.csv`
- Hydraulic:
  - `logs/mini8_hydraulic_short_20260320/column_profile_20260320_151442.csv`
  - `logs/mini8_hydraulic_short_20260320/column_summary_20260320_151442.csv`

Observed at `t = 4.0 s`:

- `runtime-mode huang`
  - `P_top_psia ~= 223.60`
  - `steady_state_score ~= 8.81`
  - `ss_max_rel_state_rate_per_s ~= 0.0264`
  - `ss_max_temp_rate_F_per_s ~= 0.924`
- `runtime-mode hydraulic`
  - `P_top_psia ~= 220.99`
  - `steady_state_score ~= 11.64`
  - `ss_max_rel_state_rate_per_s ~= 0.0349`
  - `ss_max_temp_rate_F_per_s ~= 1.014`

Interpretation:

- This is only a short open-loop comparison, not a steady-state verification.
- On this first short run, `runtime-mode huang` was slightly calmer than `runtime-mode hydraulic` by the repo's current settling diagnostics.
- That is encouraging, but not yet enough to claim that the Huang bridge is the better production path.

## Continuation checkpoint

- The sequential main-run loop was rebuilding `ColumnInputs(...)` without carrying forward:
  - `liquid_hydraulic_model`
  - `liquid_hydraulic_htc_sec`
- That meant `runtime-mode huang` was not actually preserving the Huang liquid HTC closure through the stepwise loop.
- The scaffold was updated so both sequential `ColumnInputs(...)` rebuilds now pass those fields through.
- The scaffold now also treats the generic case `Stage time constant [tau] (sec)` as too aggressive to reuse directly for Huang liquid HTC fallback:
  - explicit `Huang Liquid HTC (sec)`, `Liquid Hydraulic HTC (sec)`, or `Hydraulic Time Constant (sec)` still win
  - but if Huang would otherwise fall back only to generic stage `tau`, the runner now promotes that fallback to at least `20 s`
- The scaffold now also gives `runtime-mode huang` a hard top-drum pressure gate by default:
  - default `top_drum_pressure_gate_soft_psi = 0.0` in Huang mode
  - legacy non-Huang behavior remains `0.25 psi`
  - intent: when stage-2 to top-drum driving force goes to zero or negative, Huang should not leak `~50%` vapor slip into the drum through the soft gate
- The condenser pressure gate now feeds blocked top slip back into stage-2 vapor outflow for the Huang hybrid path, instead of routing that blocked slip into instantaneous in-condenser condensation.
- The Huang liquid-hydraulic override default is now slightly backed off when unspecified:
  - default `liquid_hydraulic_override_alpha = 0.8` in Huang mode
  - explicit CLI or workbook alpha values still win

Post-fix 60 s open-loop comparison on the same mini8 case:

- `runtime-mode hydraulic`
  - `P_top_psia ~= 223.42`
  - `steady_state_score ~= 2.02`
  - `ss_max_rel_state_rate_per_s ~= 0.00606`
  - `ss_max_temp_rate_F_per_s ~= 0.233`
- `runtime-mode huang` default case input (`liquid_hydraulic_htc_sec = 2.0 s`)
  - before safer fallback:
    - `P_top_psia ~= 472.13`
    - `steady_state_score ~= 4.11`
    - `ss_max_rel_state_rate_per_s ~= 0.0123`
    - `ss_max_temp_rate_F_per_s ~= 0.407`
  - after safer fallback promotion to `20 s`:
    - `P_top_psia ~= 299.98`
    - `steady_state_score ~= 2.27`
    - `ss_max_rel_state_rate_per_s ~= 0.00682`
    - `ss_max_temp_rate_F_per_s ~= 0.177`
- `runtime-mode huang --liquid-hydraulic-htc-sec 20`
  - `P_top_psia ~= 299.98`
  - `steady_state_score ~= 2.27`
  - `ss_max_rel_state_rate_per_s ~= 0.00682`
  - `ss_max_temp_rate_F_per_s ~= 0.177`
- `runtime-mode huang` after hard-gate default
  - `P_top_psia ~= 230.68`
  - `steady_state_score ~= 2.02`
  - `ss_max_rel_state_rate_per_s ~= 0.00605`
  - `ss_max_temp_rate_F_per_s ~= 0.187`
  - `V_to_top_drum_lbmolph ~= 0.0`
- `runtime-mode huang` after blocked-slip feedback + default `alpha=0.8`
  - mini8 at `60 s`:
    - `P_top_psia ~= 230.63`
    - `steady_state_score ~= 1.80`
    - `ss_max_rel_state_rate_per_s ~= 0.00540`
    - `ss_max_temp_rate_F_per_s ~= 0.213`
  - 20-stage baseline at `60 s`:
    - `P_top_psia ~= 230.32`
    - `steady_state_score ~= 3.39`
    - `ss_max_rel_state_rate_per_s ~= 0.0102`
    - `ss_max_temp_rate_F_per_s ~= 0.420`

Interpretation after the propagation fix:

- The Huang liquid HTC path is now genuinely active in the main sequential runner.
- The current case default HTC (`2 s`) is too aggressive for this mini8 check.
- A looser Huang HTC (`20 s`) is much calmer than the default and closer to `runtime-mode hydraulic`, but it still carries materially higher top-pressure drift.
- The hard top-drum gate removes most of that remaining top-pressure inflation on this short mini8 check and brings Huang essentially in line with the current hydraulic baseline by the repo's settling score.
- Longer/larger follow-up:
  - mini8 at `120 s` with current Huang defaults:
    - `huang`: `P_top_psia ~= 230.63`, `steady_state_score ~= 2.51`, `ss_max_temp_rate_F_per_s ~= 0.111`
    - `hydraulic`: `P_top_psia ~= 236.43`, `steady_state_score ~= 2.54`, `ss_max_temp_rate_F_per_s ~= 0.214`
    - on this longer mini8 check, Huang remains slightly calmer than hydraulic
  - 20-stage baseline at `60 s` with current Huang defaults:
    - `huang`: `P_top_psia ~= 230.32`, `steady_state_score ~= 3.39`, `ss_max_temp_rate_F_per_s ~= 0.420`
    - `hydraulic`: `P_top_psia ~= 219.30`, `steady_state_score ~= 2.98`, `ss_max_temp_rate_F_per_s ~= 0.281`
    - on the larger case, Huang still trails hydraulic
  - 20-stage Huang HTC sweep:
    - `10 s`, `40 s`, and `80 s` all performed worse than the current `20 s` fallback on the `60 s` check
    - so the remaining larger-case gap does not look like a simple one-parameter HTC retune
- So the next bottleneck is no longer basic Huang wiring or immediate top-drum leakage; it is broader pressure-side behavior on larger cases after the first-minute transient.

Additional March 20 follow-up:

- A Huang-only upper-section vapor-bridge experiment was tested and then reverted.
- The idea was to reduce top-section profile vapor traffic toward a pressure-based estimate when the stage-2 to top-drum driving force collapsed.
- That bridge did materially change upper internal vapor rates on the 20-stage case:
  - example at `60 s`, stage-3 `V_out_lbmolph` moved from about `8082` down to about `7405`
  - stages 4-6 also shifted substantially
- But the pressure KPIs did not improve:
  - 20-stage Huang stayed at about `P_top_psia ~= 230.32`
  - `steady_state_score ~= 3.39`
  - `ss_max_temp_rate_F_per_s ~= 0.420`
- The reason appears structural, not tuning-related:
  - Huang now uses a hard top-drum gate by default, so `V_to_top_drum_lbmolph` is already driven to `0`
  - the hydraulic pressure profile is also top-anchored to the drum pressure state
  - so changing internal upper-column vapor traffic can reshuffle `V_out` without materially moving the top-drum pressure KPI
- Conclusion from that test:
  - the next useful Huang pressure-side work is probably not another upper-section vapor-profile bridge
  - the next real lever is the top-drum / top-pressure state treatment itself, or another pressure-state coupling change that can move the anchored top pressure rather than only redistribute internal vapor rates

Additional Huang top-pressure follow-up:

- A Huang-only top-anchor blend is now in the RHS:
  - compute raw top-drum pressure from top vapor holdup as before
  - compute an unanchored hydraulic top pressure estimate
  - when Huang predicts a collapsed stage-2 to drum gate, blend the hydraulic top anchor away from the raw drum pressure toward that free hydraulic top estimate
  - keep a floor on drum influence so Huang does not fully discard the reflux-drum state
- Focused regression coverage was added for this Huang anchor-blend behavior.

Observed effect on the targeted validation cases:

- mini8 at `120 s`
  - previous Huang checkpoint: `P_top_psia ~= 230.63`, `steady_state_score ~= 2.51`
  - after Huang top-anchor blend: `P_top_psia ~= 230.13`, `steady_state_score ~= 2.55`
  - interpretation: essentially unchanged; slightly lower top pressure, slightly worse settling score
- 20-stage baseline at `60 s`
  - previous Huang checkpoint: `P_top_psia ~= 230.32`, `steady_state_score ~= 3.39`
  - after Huang top-anchor blend: `P_top_psia ~= 230.06`, `steady_state_score ~= 3.38`
  - interpretation: small movement in the right direction, but not enough to close the larger-case gap to hydraulic

Current interpretation:

- The Huang top-pressure anchor is a real lever, unlike the reverted upper-vapor bridge.
- But this first blend is only a modest improvement, not a breakthrough.
- Huang remains competitive on mini8 and still trails hydraulic on the 20-stage case.
- A stronger same-day follow-up blend was also tested and was not better than this first `0.25`-floor version, so the milder blend was kept.

Additional top-drum state follow-up:

- A Huang-only top-drum vapor-holdup relaxation is now in the RHS:
  - when Huang sees raw top-drum pressure sitting above the free hydraulic top estimate
  - and the excess is on the vapor side
  - it condenses that excess top vapor into the drum liquid holdup over the existing pressure/holdup timescale
- This is intentionally reduction-only:
  - it does not create new top vapor from the drum liquid side
  - it only removes excess vapor inventory from the drum state
- The run scaffold now also exports the new Huang top-drum diagnostics in profile/summary logs.

Observed effect on the targeted validation cases:

- mini8 at `120 s`
  - anchor-blend-only checkpoint: `P_top_psia ~= 230.13`, `steady_state_score ~= 2.55`
  - after top-drum vapor relaxation: `P_top_psia ~= 230.32`, `steady_state_score ~= 2.53`
  - interpretation: essentially neutral on mini8
- 20-stage baseline at `60 s`
  - anchor-blend-only checkpoint: `P_top_psia ~= 230.06`, `steady_state_score ~= 3.38`
  - after top-drum vapor relaxation: `P_top_psia ~= 229.95`, `steady_state_score ~= 3.28`
  - interpretation: this is the first top-drum-side change that moved the larger case by more than noise

Updated interpretation:

- The top-drum state itself is a more useful Huang lever than upper-section vapor-profile tuning.
- The improvement is still incremental, not enough to beat hydraulic on the 20-stage case.
- But this top-vapor relaxation is worth keeping as the new Huang checkpoint because it improves the larger case without materially hurting mini8.

Dedicated Huang top-drum vapor-relaxation sweep:

- A dedicated runner/RHS parameter was added:
  - `--huang-top-drum-vapor-relaxation-sec`
  - it is preserved through the sequential runner rebuild path
  - it is not forced as a global Huang default; the best setting is case-dependent
- 20-stage baseline at `60 s`:
  - `5 s`: `P_top_psia ~= 229.86`, `steady_state_score ~= 3.31`
  - `10 s`: `P_top_psia ~= 229.76`, `steady_state_score ~= 3.27`
  - `20 s`: `P_top_psia ~= 230.21`, `steady_state_score ~= 4.71`
  - `40 s`: `P_top_psia ~= 230.12`, `steady_state_score ~= 3.35`
  - best larger-case result from this sweep was `10 s`
- mini8 at `120 s` with explicit `10 s`:
  - `P_top_psia ~= 230.07`, `steady_state_score ~= 2.57`
  - compared with the current Huang top-vapor-relaxation checkpoint (`P_top_psia ~= 230.32`, `steady_state_score ~= 2.53`)
  - interpretation: slightly lower top pressure, but slightly worse mini8 settling score

Conclusion from the sweep:

- Keep the dedicated Huang top-drum vapor-relaxation parameter.
- Use `10 s` as the preferred larger-case tuning value for now.
- Do not promote `10 s` to a universal Huang default yet, because it does not improve the mini8 canary.

Longer 20-stage follow-up with the new Huang tuning:

- The next validation step was the larger-case `120 s` A/B using the best current Huang tuning from the `60 s` sweep.
- 20-stage baseline at `120 s`:
  - `huang --huang-top-drum-vapor-relaxation-sec 10`:
    - `P_top_psia ~= 229.81`
    - `steady_state_score ~= 2.88`
    - `ss_max_rel_state_rate_per_s ~= 0.00864`
    - `ss_max_temp_rate_F_per_s ~= 0.336`
  - `hydraulic`:
    - `P_top_psia ~= 214.14`
    - `steady_state_score ~= 3.37`
    - `ss_max_rel_state_rate_per_s ~= 0.00590`
    - `ss_max_temp_rate_F_per_s ~= 0.505`
- Top-drum diagnostics at the end of the Huang `120 s` run confirm the intended mechanism is active:
  - `V_to_top_drum_lbmolph = 0`
  - `V_to_top_drum_pressure_gate_scale = 0`
  - `P_top_drum_psia_raw ~= 237.04`
  - `huang_top_anchor_free_psia ~= 227.40`
  - `huang_top_anchor_weight = 0.25`
  - `huang_top_drum_vapor_relax_target_psia ~= 227.40`
  - `huang_top_drum_vapor_relax_dmv_lbmolps ~= -0.0243`

Updated larger-case interpretation:

- Huang still does not beat hydraulic on top pressure for the 20-stage case; it remains materially higher at `120 s`.
- But Huang is no longer simply "worse on the larger case":
  - it is now better on the repo's settling score
  - and materially better on maximum temperature-rate over this `120 s` check
- So the branch now has a real tradeoff on the larger case:
  - `hydraulic` gives lower top pressure
  - tuned `huang` gives gentler settling / temperature behavior
- Practical implication:
  - Huang is still a research branch for larger-case long runs, not a drop-in hydraulic replacement
  - but it is now worth pursuing for long simulations when smoother thermal behavior matters enough to justify the higher top-pressure state

Ten-minute Huang continuation on the 20-stage case:

- The tuned larger-case Huang branch was extended from `120 s` to `600 s` using:
  - `--runtime-mode huang --huang-top-drum-vapor-relaxation-sec 10`
- End state at `600 s`:
  - `P_top_psia ~= 230.02`
  - `steady_state_flag = 0`
  - `steady_state_score ~= 1.27`
  - `ss_max_rel_state_rate_per_s ~= 0.00381`
  - `ss_max_temp_rate_F_per_s ~= 0.0110`
- Interpretation:
  - the long run is much closer to steady state than the `120 s` checkpoint
  - temperature-rate is comfortably below tolerance by the end
  - the remaining blocker is relative state-rate, which is still slightly above the repo tolerance (`0.00381` vs `0.003`)
  - so Huang did not formally reach steady state by `600 s`, but it appears to be approaching it
- Late-time behavior is mostly settling with one transient bump:
  - `300 s`: score `~ 1.39`
  - `360 s`: score `~ 1.36`
  - `420 s`: score `~ 6.36`
  - `480 s`: score `~ 1.81`
  - `540 s`: score `~ 2.19`
  - `600 s`: score `~ 1.27`
- Practical read:
  - on this 20-stage case, tuned Huang looks viable for longer simulation studies
  - but it is still not a clean "already at steady state by ten minutes" branch under the current detector thresholds

Fifteen-minute Huang continuation on the 20-stage case:

- The same tuned Huang case was then extended to `900 s`.
- End state at `900 s`:
  - `P_top_psia ~= 230.12`
  - `steady_state_flag = 0`
  - `steady_state_score ~= 1.31`
  - `ss_max_rel_state_rate_per_s ~= 0.00393`
  - `ss_max_temp_rate_F_per_s ~= 0.00717`
- Interpretation:
  - extending from `600 s` to `900 s` did not produce a clean steady-state pass
  - the thermal side is essentially flat by the end
  - but the relative-state-rate criterion is still slightly above tolerance
  - the long run shows intermittent late spikes (`420 s`, `660 s`, `780 s`) rather than monotonic convergence
- So the present larger-case Huang picture is:
  - viable for long-run disturbance studies
  - not yet a robust "restart from final state and immediately remain quiet" branch under the current state coupling / detector setup

Restart workbook export:

- A helper script now exists at `tools/export_restart_workbook.py`.
- It copies a base case workbook and updates:
  - `Initial Conditions` tray `T`, `P`, `V`, `L`, `ML`, `MV`, `x`, and `y`
  - `Specifications` top/bottom liquid holdups
  - `Streams` distillate and bottoms conditions/compositions
- The `900 s` Huang-derived restart workbook was written to:
  - `sandbox/mini8/input/distillation_column_template_20stage_huang_900s_seed.xlsx`
- A one-step scaffold smoke test on that workbook passes Excel/spec validation, so it is usable as a new seed case.

Pressure-profile correction after invalid long-run Huang result:

- The earlier long-run Huang branch was found to be physically invalid on the 20-stage case:
  - tray pressure was being forced toward a near-flat top-anchored profile
  - even though the free hydraulic tray drops were much larger
- Root cause in the repo implementation:
  - `runtime-mode huang` still used the hydraulic pressure solver
  - but it also scaled tray pressure drops to a reflux-drum top anchor
  - and applied Huang-only top-drum vapor relaxation toward that anchored target
  - with the hard top-drum gate active, that combination could collapse the tray pressure gradient
- The Huang pressure path was corrected as follows:
  - keep the tray pressure on the free hydraulic profile when `runtime-mode huang` has no explicit top anchor
  - disable top-pressure ordering lift for Huang's free-pressure path
  - disable Huang top-drum vapor relaxation unless an explicit top anchor is provided

Observed effect on the 20-stage tuned Huang case:

- Corrected Huang at `120 s`:
  - `P_top_psia ~= 227.87`
  - `steady_state_score ~= 2.44`
  - stage pressure profile is now physically graded:
    - stage 1 `~ 227.43 psia`
    - stage 10 `~ 230.23 psia`
    - stage 20 `~ 232.00 psia`
- Corrected Huang at `300 s`:
  - `P_top_psia ~= 227.87`
  - `steady_state_score ~= 1.05`
  - `ss_max_rel_state_rate_per_s ~= 0.00314`
  - `ss_max_temp_rate_F_per_s ~= 0.0936`
  - stage pressure profile remains physically graded:
    - stage 1 `~ 227.30 psia`
    - stage 10 `~ 230.23 psia`
    - stage 20 `~ 232.07 psia`
  - the corrected branch briefly reached `steady_state_flag = 1` around `240 s` before drifting slightly back above the relative-state-rate threshold by `300 s`

Updated interpretation after the pressure correction:

- The previous `600-900 s` Huang pressure-flat runs should not be used as evidence against Huang itself; they were invalid under the repo's old top-anchored Huang pressure implementation.
- The corrected Huang branch is not yet a full reproduction of the paper's method, but it no longer exhibits the obvious unphysical pressure-profile collapse on the 20-stage case.
- This makes the Huang branch a valid candidate for further larger-case comparison work again, now that the pressure profile is physically plausible.

Corrected 20-stage Huang long run at `900 s`:

- The corrected free-pressure Huang branch was then run to `900 s`.
- End state at `900 s`:
  - `steady_state_flag = 1`
  - `steady_state_score ~= 0.627`
  - `ss_max_rel_state_rate_per_s ~= 0.00188`
  - `ss_max_temp_rate_F_per_s ~= 0.00334`
  - `P_top_psia ~= 227.87`
  - `P_bot_psia ~= 232.06`
- Final pressure profile remained physically graded:
  - stage 1 `~ 227.39 psia`
  - stage 10 `~ 230.34 psia`
  - stage 20 `~ 232.06 psia`
- Final distillate / bottoms snapshot:
  - distillate: `T ~= 117.93 F`, holdup `~ 1233.36 lbmol`, `x_propane ~= 0.8317`
  - bottoms: `T ~= 216.43 F`, holdup `~ 688.93 lbmol`, `x_pentane ~= 0.1082`
- Long-run interpretation:
  - after removing the invalid Huang top-anchor pressure forcing, the 20-stage Huang branch can now reach the repo's steady-state criteria on the larger case
  - the long-run Huang pressure profile is no longer obviously nonphysical
- Corrected restart workbook from this valid branch:
  - `sandbox/mini8/input/distillation_column_template_20stage_huang_freep_900s_seed.xlsx`
  - use this file for new 20-stage Huang disturbance studies
  - do not reuse the older `...huang_900s_seed.xlsx` workbook from the invalid pressure-flat branch
