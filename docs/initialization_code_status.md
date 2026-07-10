# Initialization Code Status

Updated: 2026-07-08

This note classifies the current initialization-related code after the ChemSep steady-state startup work showed that raw steady profiles are not model-consistent dynamic initial conditions.

Current model-state note: `docs/dynamic_model_current_state_2026-07-08.md`.

## Position

ChemSep and other steady-state exports are seed data, not accepted dynamic initial states.

Do not claim that a full-topology dynamic case is initialized only because a run starts, a steady-state flag turns on, or a diagnostic path suppresses derivatives. A valid initialized state must pass the active model's residual gates with the same topology, thermo, boundary states, vapor states, energy states, and feed treatment that the later dynamic run will use.

## Supported

These tools and paths remain part of the intended workflow.

| Item | Status | Purpose |
|---|---|---|
| `tools/column_initialization_residual_audit.py` | Supported | First gate for imported or generated seeds. Evaluates `column_rhs_v1.py` at `t=0` and ranks state-rate, material, and energy residuals. It can now audit a native checkpoint with `--init-from-checkpoint`, using the Excel workbook only as the case/layout source and restoring checkpoint runtime memory before the one-shot RHS call. |
| `tools/evaluate_initialization_dynamic_gate.py` | Supported | Dynamic acceptance gate for initializer candidates. It checks whether a seed survives a short launch without unacceptable score, rate, temperature, or endpoint drift. |
| `tools/top_boundary_liquid_coupling_audit.py` | Supported diagnostic | Isolates top-boundary liquid composition coupling and reports condenser/reflux-drum liquid mismatch without relying on tray-specific assumptions beyond the top boundary. |
| `tools/audit_energy_vapor_closure.py` | Supported diagnostic | Read-only RHS audit for the current closure hypothesis. Ranks generic vapor-flow interfaces by calc/used flow mismatch, adjacent vapor enthalpy discontinuity, pressure/holdup mismatch, K/y closure, and temperature-rate terms. |
| `tools/audit_vapor_transport_after_projection.py` | Supported diagnostic | Read-only profile audit for the post-projection first step. Ranks vapor-composition drift, K-state mismatch, and generic vapor-composition interfaces without recomputing thermo or changing the RHS. |
| `tools/audit_vapor_inventory_rate.py` | Supported diagnostic | Read-only profile audit for first-step vapor component inventory rates. Ranks finite-difference vapor inventory motion and estimates the vapor-convective contribution from adjacent stages. |
| `tools/audit_vapor_rhs_material_terms.py` | Supported diagnostic | Read-only profile audit for live RHS vapor material terms. Ranks explicit vapor component derivatives and decomposes them into transport, feed, terminal adjustment, holdup relaxation, and equilibrium transfer terms. |
| `tools/audit_time_resolved_vapor_drift.py` | Supported diagnostic | Read-only profile audit for tracking vapor RHS material terms, K-state mismatch, vapor target mismatch, and boundary diagnostics across logged times. Use caller-provided stage/time filters for focused reviews; do not hard-code interior stage assumptions. |
| `tools/audit_vapor_transport_equilibrium_conflict.py` | Supported diagnostic | Read-only profile audit comparing pre-equilibrium vapor transport RHS against the equilibrium transfer needed to cancel it. Helps distinguish under-cancellation from over-correction/fighting behavior. |
| `tools/audit_k_state_drift.py` | Supported diagnostic/gate | Read-only profile audit for time-resolved `K_state` versus `K_thermo` drift. Use it with absolute K-delta and trend limits because the rate-based dynamic gate can pass while K-level consistency worsens. |
| `tools/score_dynamic_one_step_initialization.py` | Supported diagnostic scorer | Scores completed one-step launch runs using summary metrics plus vapor RHS, cancellation coverage, and vapor-composition drift. This is the objective surface future initializer optimizers should target. |
| `tools/rank_dynamic_one_step_initialization_candidates.py` | Supported diagnostic ranker | Scores and ranks completed one-step candidate run directories. Unscorable older runs without RHS material diagnostics are retained in the report instead of aborting the ranking. |
| `tools/initialize_column_model_consistent_seed.py` | Supported workflow, pending accepted seed | Repeatable initializer orchestration: audits the input, runs named coupled reconciliation candidates, audits each candidate, selects the best workbook by explicit criteria, and writes a summary. It now also writes a requirements-aligned `initializer_<case>_<timestamp>.log` execution log with run metadata, commands, milestone metrics, artifact paths, explicit `clean_usable_assessment`, accepted-artifact selection, restart command, and final decision status. `--enable-dynamic-gate` adds baseline/candidate dynamic smoke runs plus `tools/evaluate_initialization_dynamic_gate.py` comparison before the final decision; when a candidate is clean/usable and its smoke run produced a native checkpoint, that checkpoint is reported as the preferred accepted artifact. `--enable-checkpoint-reload-gate` reloads that checkpoint through `--init-from-checkpoint` and gates the reload trajectory against the accepted candidate smoke. Current named candidates include coupled tray/top-boundary reconciliation and bottom-boundary-balanced continuation. |
| Top-boundary diagnostics in `column_rhs_v1.py` | Supported | Reports reflux-drum liquid splits such as `top_L_cond_in_*`, `top_L_reflux_out_*`, `top_L_distillate_out_*`, and `top_L_net_*`. |
| Source-topology validation flags | Supported for validation only | `--disable-boundary-states`, `--disable-vapor-states`, and `--no-equilibrium` remain valid when deliberately matching a source model such as Skogestad Column A or the narrow Gani/ChemSep material-parity case. |
| Total-condenser dry-boundary routing | Supported | A dry stage-1 total-condenser placeholder should route condensate using the actual condensed stream mixture, not a stale tray-liquid composition. |
| Native checkpoint capture/load | Supported continuation path | Completed runs now write a `.npz` checkpoint alongside the Excel restart workbook. `--init-from-checkpoint` reloads the packed dynamic state after layout checks and restores selected pressure, temperature, thermo, feed-flash, and boundary-cache memory without Excel cell round-tripping. |
| `tools/build_checkpoint_guided_seed.py` | Supported diagnostic/export bridge | Builds an Excel seed by blending an existing workbook toward a quiet profile/checkpoint-derived run. Useful for audits and interoperability, but not an accepted initializer by itself because Excel reload does not preserve all native runtime memory. |

## Experimental

These are useful research tools, but their outputs are not accepted golden seeds by themselves.

| Item | Status | Current Interpretation |
|---|---|---|
| `tools/optimize_column_initialization_residual.py` | Experimental diagnostic only | Useful for testing which degrees of freedom reduce residuals. The latest vapor-flow/energy-closure objective reduced optimizer norm but worsened the physical audit, so broad residual reweighting should not be treated as the next acceptance path. |
| `tools/reconcile_column_vapor_closure_seed.py` | Experimental diagnostic | Helpful for understanding explicit vapor-state closure defects; not a production initializer. |
| `tools/reconcile_column_liquid_energy_seed.py` | Experimental diagnostic | Fast and informative for scoped liquid/energy objectives; does not by itself control explicit vapor-state waves. |
| `tools/reconcile_vapor_material_transport_seed.py` | Experimental diagnostic only | Tests whether vapor compositions alone can reconcile live vapor material-transport RHS terms. The first trial improved the static RHS but failed the dynamic smoke, so it is not an acceptance path in its current form. |
| `tools/solve_pressure_flow_closure.py` | Experimental diagnostic | Pressure-flow closure is necessary but insufficient without vapor composition, vapor inventory, and energy consistency. |
| `tools/optimize_column_profile_coefficients.py` | Experimental diagnostic | Smooth profile corrections are better behaved than local windows but have not exposed the missing closure alone. |
| `--init-top-liquid-condensate-blend` | Experimental diagnostic | Useful for testing whether reflux-drum liquid mismatch explains startup failure. A full blend reduced the targeted top-liquid residual but still failed the dynamic gate. |
| `--dynamic-vflow-nominal-hi-ratio` | Experimental diagnostic | Useful for probing vapor-flow limiter sensitivity. The first narrow ceiling probe slightly reduced a local vapor-flow mismatch but worsened dynamic score, peak score, and temperature behavior. |
| `--runtime-mode total-reflux` | Experimental startup recipe | Mechanically viable and useful for probes, but not an accepted shortcut to a golden seed for the current C3/C4 case. |
| `--enable-startup-vapor-homotopy` | Experimental startup transition | Useful infrastructure for later vapor-closure transitions; current evidence shows the C3/C4 failure can occur before vapor beta activates. |
| `--startup-total-reflux-washout-sec` | Experimental diagnostic | Helps test reflux-drum washout behavior; short and 300 s washout probes did not produce an accepted seed. |

## Deprecated For Acceptance

These paths may remain temporarily for comparison, but they must not be used as evidence of rigorous initialization.

| Item | Status | Reason |
|---|---|---|
| Raw ChemSep profile marching | Deprecated | Raw `T/P/x/y/L/V` profiles can be steady in ChemSep and non-steady under this model's explicit boundary, vapor, pressure, and energy equations. |
| Freezing tray vapor derivatives as an acceptance path | Deprecated | It can make derivative metrics look quiet while liquid/composition profiles drift outside validation tolerance. |
| Local-only profile nudging without interface/global penalties | Deprecated for acceptance | Prior trials moved residuals inward rather than eliminating them. |
| Treating `steady_state_flag` as validation | Deprecated | The flag is diagnostic only. Validation requires source comparison or explicit case-specific residual/KPI gates. |

## Current Next Direction

Stop broad residual-solver tuning in its current form.

The current accepted-seed direction is checkpoint-oriented: use residual audits, one-step/dynamic scoring, and targeted least-squares/projection steps to find a model-consistent state, then preserve the accepted packed state and runtime memory with native checkpoint serialization. Excel workbooks remain useful seed and review artifacts, but an Excel-only export must prove reload parity before it can be treated as a production initializer output.

2026-07-08 timeout update: the current best dynamic behavior is the 900 s C3/C4 linear-steady/equilibrium-guard checkpoint recipe. It is a useful working baseline, not a zero-residual accepted initializer. The no-energy checkpoint reload and liquid-holdup projection/solve probes show that the remaining blocker is vapor/material/pressure coupling during runtime, not simply stored energy-state projection or liquid-holdup fitting. The internal liquid-holdup projection/least-squares branch should be closed unless a later audit changes the residual ranking.

2026-07-08 external-review follow-up: the 900 s run's worst-state pulses move across many stages and both tray phases while the envelope damps, which supports treating that case as coupled transient behavior. By contrast, the no-energy reload and checkpoint residual family is more localized and repeatable, so it should get a focused vapor-material root-cause audit before any broader implicit-solve architecture work is treated as necessary. The no-energy reload is also a degraded-state restart test; avoid using it alone as evidence that the full-state dynamic model is structurally unsound.

2026-07-08 1800 s gate result: the cheap longer gate showed the 900 s envelope was not safely damped. The same linear-steady/equilibrium-guard recipe failed the 1800 s run, rebuilding after about 920 s and jumping from score `~6.09` at 1200 s to `~538` at 1240 s. Focused audits at 1240 s show stage 12/13 vapor transport and energy residuals activate together; `V_calc - V_used` remains zero, so this is not vapor-flow lag. The active next initializer/model task is to diagnose that 1200-1240 s feed-adjacent coupling transition.

2026-07-08 K-level gate addendum: `tools/audit_k_state_drift.py` was added because the 900 s rate-based dynamic gate can pass while K consistency worsens. On `logs/c3c4_stage2_liq_eq_vap_linearsteady_900s_eqcompguard_m1_20260708`, the new audit fails: final max `|K_state - K_thermo| ~= 1.647`, final max `|ln(K_state/K_thermo)| ~= 1.932`, and regrowth from the run minimum is `~0.745`. The final worst row is generic interior stage 5, n-pentane. Future accepted seeds must pass this level-consistency gate in addition to rate-based dynamic smoke checks.

2026-07-08 equilibrium-transfer guard addendum: comparing existing 300 s runs confirms the tradeoff. The explicit `--equilibrium-component-transfer-max-cancel-multiplier 1.0` run is dynamically calmer (`final score ~= 2.26`, `peak score ~= 22.68`) but fails K drift (`final |K_state-K_thermo| ~= 1.39`, positive trend `~0.50`). The default/sign-aware `1.5` run improves K consistency (`final |K_state-K_thermo| ~= 0.875`, positive trend `0`) but worsens the dynamic wave (`final score ~= 3.00`, `peak score ~= 50.03`) and still narrowly fails the log-ratio K gate. Interpretation: the guard is probably causing or exposing the K drift, but simply loosening it is not an accepted fix.

Latest 2026-07-08 checkpoint audit: `tools/column_initialization_residual_audit.py --init-from-checkpoint` was run on the `900 s` linear-steady/equilibrium-guard checkpoint. The native checkpoint audit is much cleaner than the checkpoint-guided Excel export (`max relative state rate 0.0215 1/s`, `max tray total material residual 2004 lbmol/h`), but it still fails the strict residual gate. The dominant residual is energy-state motion, with secondary explicit vapor-state motion. Interpretation: do not abandon native checkpoints, but do not certify this checkpoint as a zero-residual initializer. Broad least-squares remains paused; the next accepted-seed work should target the energy/vapor transport residuals exposed by the checkpoint audit.

Follow-up 2026-07-08 energy breakdown: `tools/stage_energy_residual_breakdown_report.py` now supports `--init-from-checkpoint` and reports the B1 energy-state derivative beside the temperature-state and vapor-flow energy diagnostics. With vapor-flow relaxation disabled, the vapor-flow calc/used mismatch is removed, but the B1 energy-state residual remains large. A diagnostic checkpoint projection that reset `tray_EL_BTU` and `tray_EV_BTU` to material holdup times checkpoint `HL/HV` made the residual worse (`max relative state rate ~0.0217 1/s`, worst energy state moved to another generic interior stage). Interpretation: do not use direct EL/EV enthalpy projection as the accepted fix. The remaining problem is a deeper inconsistency between the energy-state transport equation and the temperature/vapor-flow energy closure, not merely stale stored energy values.

No-energy checkpoint probe: `tools/strip_checkpoint_energy_state.py` converts an energy-state native checkpoint into a temperature/vapor-flow checkpoint by removing only `tray_EL_BTU` and `tray_EV_BTU` from the packed state. The converted `900 s` checkpoint removes the B1 energy-state residual family from the audit, but still fails the strict residual gate on vapor/material motion (`max relative state rate ~0.0116 1/s`, `max tray total material residual ~1374 lbmol/h`). A `60 s` reload remained bounded and thermally quiet (`score ~1.16`, `max temp rate ~1.4e-8 F/s`) but was not steady (`max relative state rate ~0.00348 1/s`) and top pressure drifted downward. Interpretation: the initializer acceptance path should keep B1 energy states out for now, but the remaining acceptance blocker is vapor/material/pressure drift, not thermal blow-up.

The next useful work is an equation/topology review of the energy and vapor-flow closure that the initializer is trying to satisfy. The residual optimizer, top-boundary liquid audit, vapor-flow ceiling, checkpoint-guided seed export, and dynamic gate should remain diagnostics for that review, not independent attempts to tune an accepted seed.

Current 2026-07-07 provenance result: energy vapor-flow pressure basis is not the dominant mismatch at startup, and provider enthalpy precedence has been corrected. The `K_eq_relax` diagnostics show that the reported `K_state/K_thermo` mismatch is not merely a stale diagnostic basis; the explicit vapor composition state is still away from the model's equilibrium target. However, in composition-only relaxation mode the interior `y_state-y_target` gap is modest (`~0.040 max` in the one-step smoke), while the dry total-condenser row creates a large boundary-only `y_target` artifact that should not be read as an interior tray failure.

A no-lag vapor-flow probe (`--vapor-flow-relaxation-sec 0`) removed the calc/used vapor-flow mismatch (`1187.6 lbmol/h` to `0`) and reduced normalized energy residual (`2.01 F/s` to `1.42 F/s`), but did not pass the dynamic launch gate and left a temperature-rate spike (`~0.52 F/s`). Conclusion: vapor-flow lag is a real contributor and diagnostic lever, but not a standalone initializer fix.

Follow-up equation audit found that the energy vapor-flow closure was solving a reference-invariant tray energy equation, while the legacy temperature-state block still used an absolute-enthalpy form on generic interior trays. These forms disagree whenever startup material rates are nonzero. The generic interior temperature-state balance now uses the same `hL_out` reference form as the vapor-flow closure. In a one-step no-lag smoke this reduced the raw tray temperature-rate maximum from about `0.52 F/s` to about `0.057 F/s`; the dynamic launch still fails on vapor-state residuals, so this is a real RHS consistency fix, not an accepted initializer.

The vapor-flow temperature-rate target policy is now explicit in the runner: use `--vapor-flow-zero-temperature-target` (alias `--vflow-zero-dt-target`) to make the energy vapor-flow closure target zero tray temperature rate instead of the previous step's `last_dT_tray` memory. This excludes that dynamic temperature-rate memory from initialization diagnostics. It does not disable physical equilibrium relaxation; use `--no-equilibrium` separately when a no-relaxation RHS audit or launch is desired.

The first zero-temperature-target/no-lag smoke (`logs/c3c4_stage2_zero_dt_target_nolag_smoke_20260707`) confirmed that the dynamic memory can be excluded: `V_calc - V_used` stayed at `0`, and the logged vapor-flow target was `0 F/s`. However, the strict target exposed a remaining energy/thermo inconsistency rather than producing an accepted seed: max raw tray temperature rate rose to about `0.222 F/s`, dominated by the top interior tray interface, and the audit still reports equilibrium K-state mismatch. Conclusion: removing relaxation/memory is the right diagnostic posture for steady initialization, but it is not sufficient as the initializer fix.

A term-level follow-up added temperature-state energy diagnostics beside the vapor-flow closure terms. The stage-2 mismatch was localized to the liquid enthalpy entering from the top boundary/stage-1 side: vapor-flow closure used about `-3840 BTU/lbmol`, while the temperature-state live refresh used about `-3995 BTU/lbmol`. With reflux near `5967 lbmol/h`, that difference explained the observed `~256 BTU/s` term gap and `~0.222 F/s` temperature-rate spike. Forcing scalar refresh of the top liquid in the vapor-flow helper did not change the logged launch result, proving the issue was not just batch-cache staleness.

The top-boundary liquid enthalpy ownership has now been corrected for the reflux stream entering the first interior stage below the top boundary. When explicit top boundary liquid exists, both the energy vapor-flow closure and the temperature-state balance use the top accumulator liquid composition, top tray temperature, and top tray pressure for that incoming reflux enthalpy. The strict no-lag/zero-temperature-target smoke (`logs/c3c4_stage2_top_reflux_enthalpy_owner_smoke_20260707`) reduced max raw tray temperature rate from about `0.222 F/s` to `1.44e-7 F/s`, and reduced the temperature/vapor-flow term mismatch from about `256 BTU/s` to `1.65e-4 BTU/s`. This is a real RHS consistency fix, but not an accepted initialization: the same audit now identifies equilibrium K-state/vapor-composition mismatch as the dominant remaining family.

An opt-in tray vapor equilibrium projection has been added for explicit restart diagnostics: `--init-align-tray-vapor-to-equilibrium` preserves tray vapor holdup totals but repacks vapor component splits from the live RHS `y_target_tray`, and `--init-tray-vapor-equilibrium-blend` controls the blend. On the strict one-step C3/C4 smoke (`logs/c3c4_stage2_vapor_eq_align_smoke_20260707`) this reduced the launch score from `138.38` to `26.06`, max relative state rate from `0.415/s` to `0.0782/s`, and the interior `y_state-y_target` maximum from about `0.040` to `0.0035`. This is clear progress, but not acceptance: K-state mismatch remains dominant after the first dynamic step.

A matching tray liquid equilibrium projection has also been added (`--init-align-tray-liquid-to-equilibrium`, `--init-tray-liquid-equilibrium-blend`). Full liquid+vapor projection (`logs/c3c4_stage2_liqvap_eq_align_smoke_20260707`) did not improve the one-step score beyond vapor-only (`26.08` vs `26.06`), though it reduced the temperature-rate criterion (`0.0833 F/s` vs `0.103 F/s`). Treat this as diagnostic infrastructure, not the next rabbit hole. The immediate useful branch is vapor-state projection plus a follow-up material/transport audit explaining why the projected state is pulled off the K manifold.

The follow-up first-step transport audit (`tools/audit_vapor_transport_after_projection.py`, report `logs/vapor_transport_after_projection_audit_vapor_eq_align_20260707.md`) shows that the vapor projection largely holds: after the first `0.2 s`, max interior `|y-y_target|` is only `0.00350`, while max `|ln(K_state/K_eq)|` remains `0.588`. The remaining K mismatch should therefore not be interpreted primarily as failed vapor-composition projection. It points to liquid composition, K-basis, or material/transport closure around the same generic vapor interfaces.

The initial profile logger has also been corrected so a diagnostic-free `t=0` snapshot uses the current unpacked vapor state (`u["y_tray"]`) rather than falling back to `col.y0`. This matters for projection audits because the previous fallback could make the initial profile row look pre-projection even though the runtime state had already been repacked. A corrected-log one-step run (`logs/c3c4_stage2_interior_liq_vapor_eq_align_smoke_loggingfix_20260707`) reproduced the same dynamic result (`score=26.08`, `ss_max_rel_state_rate_per_s=0.0782/s`, `ss_max_temp_rate_F_per_s=0.0833`) but clarified the mechanism. The vapor inventory audit (`logs/vapor_inventory_rate_audit_interior_liq_vapor_eq_align_loggingfix_20260707.md`) shows that the worst interior vapor rate is explained almost entirely by vapor convection across adjacent composition gradients (`tray_V` stage 3 n-Butane, `0.0782/s`, estimated convective term `0.203 lbmol/s` versus finite-difference `0.207 lbmol/s`). This is evidence to stop tuning liquid/vapor equilibrium projection and move to a vapor material-transport reconciliation.

The RHS now logs vapor material-term arrays for explicit tray vapor states:
`tray_V_transport_in/out_lbmolps`, `tray_V_feed_lbmolps`,
`tray_V_terminal_adjust_lbmolps`, `tray_V_holdup_relax_lbmolps`,
`eq_transfer_lbmolps_tray`, `tray_V_pre_equilibrium_rhs_lbmolps`, and
`tray_V_final_rhs_lbmolps`. The term audit on the refreshed RHS-term smoke
(`logs/vapor_rhs_material_terms_audit_interior_liq_vapor_eq_align_20260707.md`)
confirms the live mechanism. At `t=0.2 s`, the worst interior explicit vapor
RHS is `tray_V` stage 3 n-Butane at `0.0454/s`: pre-equilibrium transport is
`+0.203 lbmol/s`, equilibrium transfer damps it by `-0.0827 lbmol/s`, and the
remaining final RHS is `+0.120 lbmol/s`. Conclusion: equilibrium relaxation is
not the source of the remaining failure; it is partially opposing a vapor
transport imbalance. The next initializer branch should reconcile explicit
vapor inventories/compositions with the live vapor traffic, or identify a
transport-equation defect if that reconciliation proves impossible.

That branch has now been tested in its narrowest form with
`tools/reconcile_vapor_material_transport_seed.py`, varying only interior tray
vapor composition splits while preserving vapor holdup totals. Trial 1 reduced
the static maximum relative vapor RHS from `0.0799/s` to `0.0175/s` with maximum
vapor composition drift of `0.00868`, but it did not produce a usable dynamic
seed. The one-step smoke with the usual liquid/top alignment worsened to
`score=56.36`, `rel=0.169/s`; the no-reprojection smoke worsened further to
`score=249.82`, `rel=0.749/s`. Call off the simple vapor-composition-only
static material reconciliation branch. The useful lesson is that the remaining
problem is coupled vapor transport plus equilibrium-target motion; any further
optimizer must use a dynamic one-step objective or include liquid/K-basis
consistency, otherwise it is optimizing the wrong surface.

A follow-up conflict audit (`tools/audit_vapor_transport_equilibrium_conflict.py`)
confirms the failure mode. On the projected one-step run
(`logs/vapor_transport_equilibrium_conflict_interior_liq_vapor_eq_align_20260707.md`),
the median cancellation coverage is `0.371`: equilibrium transfer is usually
damping the transport RHS but not fully canceling it. On the failed reconciled
candidate
(`logs/vapor_transport_equilibrium_conflict_reconciled_trial1_smoke_20260707.md`),
the median coverage jumps to `3.26`, and the leading rows show large
over-cancellation. That means the simple static solve pushed the equilibrium
target/transport balance past the dynamic sweet spot. The next trial should not
increase static solve effort; it should either optimize a one-step dynamic gate
or review the coupled vapor transport/equilibrium equations.

`tools/score_dynamic_one_step_initialization.py` now turns that rule into a
repeatable one-step objective over completed launch runs. It combines the
summary score, relative state rate, temperature rate, max vapor RHS,
cancellation-coverage error, overcoverage, and vapor-composition drift. On the
current projected one-step run it reports objective `27.28`; on the failed
vapor-material reconciled candidate it reports `59.77`, with the latter
penalized by high dynamic score, larger vapor RHS, larger drift, and maximum
overcoverage of `19.78`. Future initializer search should target this dynamic
score surface instead of a static RHS norm.

`tools/rank_dynamic_one_step_initialization_candidates.py` applies the same
score to a bounded set of completed run directories. The first ranking
(`logs/dynamic_one_step_candidate_ranking_20260707.md`) found no existing
candidate that beats the projected RHS-terms baseline: the baseline remains
best at `27.28`, the vapor-material reconciled smoke scores `59.77`, and the
no-reprojection reconciled smoke scores `261.38`. Older projection runs without
the live RHS material-term columns are listed as unscorable, which is expected.
Next search work must generate new candidates under this dynamic objective
rather than reusing the failed static reconciler output.

A small bounded projection-blend probe was then run with tray liquid equilibrium
alignment plus tray vapor equilibrium blends of `0.75` and `0.50`. Both runs
scored essentially the same (`27.2799`) and only barely improved on the
projected RHS-terms baseline (`27.2837`). Their metadata shows the vapor
projection step was nearly a no-op by then (`max_composition_delta` around
`1e-10`), so further vapor-blend tuning is not a productive branch. This is a
minor diagnostic improvement, not an accepted initializer and not evidence to
resume projection sweeps.

The next equation-based initializer branch was fruitful. An opt-in tray vapor
linear-steady projection has been added:
`--init-align-tray-vapor-to-linear-steady`,
`--init-tray-vapor-linear-steady-blend`, and
`--init-tray-vapor-linear-steady-scope`. It preserves each tray vapor holdup
total and targets the local composition implied by the live RHS vapor transport
terms plus the equilibrium source term, rather than forcing `y` directly to the
equilibrium target. On the strict one-step C3/C4 launch
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_rhs_terms_20260707`), the dynamic
one-step objective improved from the projected RHS-terms baseline `27.2837` to
`6.18033`; the runner score dropped from about `26.08` to `5.84`, max relative
rate from `0.0782/s` to `0.0175/s`, max vapor RHS from `0.1619` to
`0.0478 lbmol/s`, and median cancellation coverage moved from `0.3708` to
`0.9054`. Metadata confirms the projection was active (`max_composition_delta`
about `0.00793`) and repacked vapor energy.

A short `10 s` smoke with the same initializer
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_10s_20260707`) did not blow up; the
runner score decayed from `5.84` at the first logged step to `1.30` at
`10.0 s`, with max relative rate dropping to `0.00389/s`. This is not final
acceptance, but it is enough evidence to stay on the linear-steady vapor
projection path and test longer dynamic gates before returning to broader
equation changes.

The first `60 s` extension exposed a separate runtime pressure-boundary defect:
with the top-anchor command fixed at `222.62 psia`, the reported top hydraulic
pressure drifted to `226.15 psia`. The late vapor-composition failure followed
that pressure drift. The cause was the top pressure ordering guard in the RHS:
after the hydraulic profile was built with an explicit top anchor, the guard
could lift the entire tray pressure profile back above the raw top-drum pressure
state. That defeated the explicit anchor. The guard now uses the explicit top
anchor as the ordering reference when one is active, while retaining the raw
top-drum pressure as a diagnostic.

After that fix, the same `60 s` launch
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_60s_topanchorfix_20260707`) passes
the runner steady-state check. The hydraulic top pressure stays at
`222.62 psia`; the score decays from `1.85` at `5 s` to `0.560` at `60 s`;
max relative state rate falls to `0.00168/s`; the vapor RHS audit at `60 s`
reports max relative vapor RHS `0.000993/s`; and the energy/vapor closure audit
reports `V_calc - V_used = 0` and max raw energy temperature rate
`2.4e-15 F/s`. This keeps the linear-steady vapor initializer on the productive
path and identifies top-anchor pressure ordering as a real RHS bug, not an
initializer limitation.

The longer `300 s` extension is now classified as a separate runtime-coupling
failure rather than an initializer failure. With the top-anchor ordering fix,
the linear-steady initializer remains quiet through about `120 s`, then the live
condenser condensed flow jumps from about `8655 lbmol/h` to about
`12245 lbmol/h` around `140 s` and the run deteriorates afterward. Follow-up
time-resolved audit corrected the first interpretation of that symptom: in the
logged strict total-condenser run, `V_to_top_drum_lbmolph` is `0` at every
logged time and the vapor-slip pressure gate scale is blank/NaN, so the
top-drum vapor-slip/gate branch is not the direct cause. The condenser surge is
downstream of a broader vapor-traffic change. Around the same onset, the
feed-region energy residual over heat capacity jumps from about `0.185 F/s` at
`120 s` to about `6.08 F/s` at `140 s`, then about `9.43 F/s` at `160 s`; by
`160 s`, the dominant vapor RHS rows are in generic interior stages near the
feed/lower-column transition, with large K-state and vapor-target drift.
Conclusion: do not continue level-control tuning or top vapor-slip/gate tuning
as the main branch. The next fix should inspect the generic interior
energy/vapor-flow/equilibrium coupling that produces the `140 s` vapor-traffic
change, while keeping top and bottom boundary handling generic and
topology-based.

The next generic RHS correction is now in place as an equilibrium
component-transfer guard. It limits the row-wise equilibrium component-transfer
vector against the local pre-equilibrium vapor material RHS, preserving
liquid/vapor equal-and-opposite transfer while preventing a single component
from overdriving the vapor inventory equation. The limiter is sign-aware:
transfers that oppose the pre-equilibrium RHS can cancel up to the configured
multiplier, while same-direction transfers get only the excess allowance above
`1.0`. The knobs are exposed as
`--equilibrium-component-transfer-max-cancel-multiplier` and
`--equilibrium-component-transfer-floor-lbmolps`.

The best current `300 s` C3/C4 dynamic gate uses the linear-steady vapor
initializer, the top-anchor ordering fix, no feed reflash, and
`--equilibrium-component-transfer-max-cancel-multiplier 1.0`
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_m1_20260708`).
It still fails the strict steady-state gate, but the final score is `2.26`
with final relative rate `0.00679/s`, and the worst wave is down to about
`22.7` near `155 s`. The worst remaining audit is now mostly vapor transport,
not equilibrium-transfer amplification. This is progress, but not model-health
acceptance.

`tools/audit_vapor_transport_pulse.py` now diagnoses the remaining transport
waves from profile CSVs. It ranks component pulses and estimates whether the
live transport term is mostly vapor traffic, upstream/downstream vapor
composition gradient, or mixed transport. On the best `300 s` run, the `155 s`
pulse is a composition-gradient wave carried by high vapor traffic, not a fresh
equilibrium-relaxation failure. A partial `600 s` extension reached about
`390 s`; the score had fallen to `1.73`, and the transport pulse audit at
`390 s` reported max relative vapor RHS about `0.00377/s`. This suggests the
current remaining behavior is a long damped startup transient. Do not add a
generic transport limiter unless a longer completed gate shows non-damping or
unphysical recurrence.

The completed sparse `900 s` gate is now the best dynamic evidence
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_900s_eqcompguard_m1_20260708`).
It passes at the endpoint with score `0.969`, relative state rate
`0.00291/s`, and temperature rate `0 F/s`. The largest early pulse remains
near `200 s` (`score=14.0`), but the envelope decays: after `600 s`, the
largest pulses are `720 s` (`score=3.15`) and `860 s` (`score=2.31`), and the
run is back below the steady-state gate by `880-900 s`. Pulse audits at `720 s`
and `860 s` show the same generic mixed vapor-transport family, with max
relative vapor RHS about `0.00930/s` and `0.00684/s`. This is the first
longer-window pass for the current initializer/runtime recipe.

The later `1800 s` extension and the `1300 s` fine trace invalidate that
recipe as an accepted long-horizon state. The fine trace
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_1300s_eqcompguard_m1_fine_20260709`)
shows a smooth buildup to score `6.09` at `1200 s`, then a jump to about
`438.7` by `1205 s`. `tools/audit_liquid_inventory_depletion.py` now captures
the precursor: one internal tray liquid inventory reaches `0.208 lbmol` at
`1200 s`, followed by a `0.972` liquid-composition step. This means the active
failure is no longer just K-state drift or vapor transport. The current
initializer recipe lets a small profile-flow imbalance slowly drain an internal
liquid inventory until the explicit composition update becomes timestep
sensitive.

Feed-stage flashing was re-tested after fixing a CLI propagation gap. Previously,
`--flash-feed-at-stage-conditions` was parsed but not copied into `RunnerConfig`,
so early A/B runs that appeared to test feed flashing were effectively still
using the no-feed-flash path. The runner now records the effective feed-flash
flag and feed liquid/vapor split in the profile CSV, and
`tests/test_dynamic_run_scaffold_v1.py::test_cli_feed_flash_flags_propagate_to_runner_config`
covers the CLI handoff.

With the fixed handoff, the first 300 s feed-stage flashing probe exposed a
second defect rather than a physical feed-flash result. The run
(`logs/c3c4_stage2_stagefeedflash_fixed_300s_20260709`) toggled the effective
feed vapor fraction to `0.5`, drained the feed-region liquid inventory to about
`0.1555 lbmol`, and failed the liquid-inventory audit. That 50/50 split was
then traced to an indeterminate single-phase/bubble-point flash packet:
the provider returned `K ~= 1`, so the Rachford-Rice residual was identically
zero and the bisection midpoint became the apparent vapor fraction.

The feed split logic now treats `K ~= 1` as indeterminate and falls back to the
source stream vapor fraction instead of inventing a split. For this C3/C4 feed,
that preserves the all-liquid bubble-point feed (`VF = 0.0`). A same-command
300 s rerun with feed-stage flashing enabled
(`logs/c3c4_stage2_stagefeedflash_k1fix_300s_20260709`) keeps the feed-stage
minimum liquid inventory at `38.3486 lbmol`, has max feed vapor-fraction step
`0`, and finishes with score `2.281`. Regression coverage was added in
`tests/test_column_rhs_v1.py` for both the `K ~= 1` fallback and a bracketed
two-phase split.

`tools/audit_feed_stage_equations.py` now audits the generic feed-bearing stage
from the profile CSV. The original feed-flash audit
(`logs/feed_stage_equation_audit_stagefeedflash_fixed_300s_20260709.md`) shows
that the feed-stage material accounting closes: liquid total closure residual is
`0`, feed-liquid residual is `0`, and the pre-phase liquid flow residual is
roundoff. Pressure-basis delta is also `0`. The current failure is therefore not
a simple feed-stage mass-balance coding error. The updated K=1-fallback audit
(`logs/feed_stage_equation_audit_stagefeedflash_k1fix_300s_20260709.md`)
confirms that removing the artificial feed split also removes the inventory
collapse in the 300 s probe.

Geometry-based level controllers have also been activated and tested with the
same recipe. The gentle true-level case
(`logs/c3c4_stage2_liq_eq_vap_linearsteady_900s_eqcompguard_m1_truelevel_20260708`,
`--top-level-pv-mode true-level --bottom-level-pv-mode true-level`,
`Kc=1`, `Ti=600 s`) passes the `900 s` gate with score `0.972`, relative state
rate `0.00292/s`, and temperature rate `0 F/s`. The logged PVs are geometry
fractions, not molar holdups. However, the top level still drifts from its
initial setpoint while the bottom level rises, so the current tuning should be
viewed as safe controller activation, not final level-control performance.
A stronger `300 s` probe (`Kc=4`, `Ti=300 s`) held level closer but worsened the
early vapor pulse. Controller tuning should therefore be handled after the
initializer/runtime gate, with its own closed-loop acceptance objective.

Checkpoint-guided Excel export was tested as a bridge from the accepted
`900 s` trajectory back into a reusable seed workbook. The first export exposed
generic serialization issues: profile component columns use sanitized names
such as `x_n_Propane`, while workbook component names use `n-Propane`; terminal
boundary composition columns use `Distillate_x_*`. `tools/build_checkpoint_guided_seed.py`
now handles those generic name variants, and its regression tests cover the
mapping. The corrected workbook
(`logs/c3c4_checkpoint_guided_seed_from_900s_fixed2_20260708.xlsx`) updates all
20 stage composition, liquid holdup, vapor holdup, and flow rows, plus top and
bottom liquid boundary states. Under default startup conditioning, the
`300 s` reload still failed (`score=26.5`) because startup thermo conditioning
altered the reconciled tray compositions before the first logged step. With
startup/re-entry conditioning disabled, the same workbook stayed bounded for
`60 s` (`score=1.44`, relative rate `0.00433/s`) but still underperformed the
native checkpoint restart from the same source (`score=1.16`, relative rate
`0.00348/s`). Conclusion: workbook export is useful for diagnostics and review,
but accepted initializer output should be native checkpoint-style state plus
runtime memory unless an Excel reload proves parity.

Near-term work should focus on:

- keep ChemSep or other steady-state exports as guesses only,
- inspect whether the energy-based vapor-flow closure can satisfy the same state it is asked to launch from,
- use `tools/audit_energy_vapor_closure.py` to rank the interface and term families before changing equations,
- compare vapor-flow mismatch, energy residuals, pressure coupling, and temperature-rate spikes through the RHS path,
- treat top-boundary reflux enthalpy ownership as fixed unless a future audit contradicts it,
- keep the tray vapor linear-steady projection as the current best initializer candidate,
- keep the older tray vapor equilibrium projection as a diagnostic comparison, not the active search branch,
- keep the explicit top-anchor pressure-ordering fix; do not let raw top-drum pressure diagnostics override an active top pressure anchor,
- treat the `300 s` failure as a runtime coupling issue after a good launch, not as evidence to abandon the initializer,
- inspect the generic interior energy/vapor-flow/equilibrium path that precedes the condenser-flow jump before changing top-drum vapor-slip or level-control equations,
- treat the equilibrium component-transfer guard as a productive generic RHS
  fix, with multiplier `1.0` as the current best tested setting,
- inspect the remaining transport-dominated pulse before adding more
  equilibrium-relaxation damping,
- use `tools/audit_vapor_transport_pulse.py` to distinguish composition-gradient
  waves from vapor-flow jumps before changing the transport equation,
- use the completed `900 s` dynamic gate as the current acceptance baseline,
  while recognizing that the `1300 s`/`1800 s` evidence rejects it as an accepted
  long-horizon initialization,
- include the liquid-inventory depletion audit in future acceptance evidence,
  because rate and K-level gates alone can miss a slow drift toward a
  near-empty internal liquid inventory,
- include the feed-stage equation audit whenever feed flashing or feed packet
  reuse is changed, so balance closure can be separated from timestep/inventory
  robustness,
- keep `--flash-feed-at-stage-conditions` out of current acceptance runs unless
  the feed split and liquid-inventory update are also made timestep-safe,
- use the gentle true-level controller recipe only when closed-loop inventory
  behavior is needed; do not use aggressive level-controller tuning as an
  initializer fix,
- do not chase full liquid+vapor projection unless a material/transport audit justifies the liquid-side move,
- do not continue vapor-composition-only static material reconciliation; it improved static RHS terms but worsened the dynamic launch,
- target the remaining mismatch with longer dynamic gates and the existing one-step scorer before trying another equilibrium-projection variant,
- use the dynamic gate as the acceptance criterion for any proposed fix,
- keep corrections generic and topology-based, with only top and bottom boundary-specific handling,
- prefer native checkpoints over Excel restart workbooks for preserving an accepted dynamic state,
- require the selected workbook or checkpoint to pass the active residual audit before using it as a dynamic launch seed.

If a tool writes a new workbook or checkpoint, it should be called an experimental or diagnostic seed until it passes the active residual audit and a short dynamic launch with hidden re-entry conditioning disabled.
