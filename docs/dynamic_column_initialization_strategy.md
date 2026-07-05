# Dynamic Column Initialization Strategy

Date: 2026-05-28

## Fundamental Difficulty: Why Moving from Steady-State to Dynamics Is So Notoriously Fragile

### The Problem Statement

Why is initialization so remarkably difficult when others have implemented it successfully? The short answer is that **commercial simulators have conditioned us to believe that moving from steady-state to dynamics is a simple transition, while the academic literature proves it is one of the most notoriously fragile mathematical problems in process systems engineering.**

When a platform like Aspen Dynamics or HYSYS allows a user to simply click "Switch to Dynamics," it isn't just copying and pasting a spreadsheet profile. It triggers an immense, hidden mathematical scaffolding—specifically, a **Consistent Initialization Solver**—that executes algorithms written across decades of DAE (Differential-Algebraic Equation) research.

By building an explicit vapor/energy topology from scratch in Python, you are peeling back that black box. The reason the model fights back isn't because the code is wrong; it is because we are running head-first into the structural realities outlined in published literature.

### 1. The Literature Gap: Simple Textbooks vs. Explicit Realities

If you look at standard undergraduate modeling literature or simplified papers, initialization looks easy. That is because they almost universally employ three severe mathematical simplifications:

1. **Constant Molar Overflow (CMO):** They assume vapor and liquid flow rates are constant across sections, eliminating energy balances entirely.
2. **Implicit/Incompressible Hydraulics:** They assume liquid inventories change, but vapor volume is non-existent, and pressure is either flat or fixed algebraically.
3. **Index-0 Systems:** There are no algebraic constraints that pull variables in opposite directions.

This model utilizes an **explicit vapor volume and rigorous energy topology**. In this formulation, pressure is not a static gradient; it is a differential state derived directly from the total moles of vapor crammed into a rigid, physical container volume:

$$\frac{dP_i}{dt} = \frac{R \cdot Z}{V_{\text{free},i}} \sum \frac{dn_{V,i}}{dt} + \dots$$

This transforms the column into a **stiff, Index-1 (or higher) DAE system**. In this architecture, an incredibly microscopic mass or thermal defect at $t=0$ doesn't just cause a mild flow adjustment; it creates a violent pressure shock ($dP/dt \to \infty$) because gases are highly compressed within fixed volumes.

### 2. The "Consistent Initialization" Problem (Pantelides' Algorithm)

In a seminal 1988 paper, *The Consistent Initialization of Differential-Algebraic Systems* (C.C. Pantelides), and subsequent work by Paul Barton and Lorenz Biegler, the exact trap you uncovered with the `top-anchor` mode is mathematically defined.

For a system of DAEs written as:

$$F(x, \dot{x}, y, t) = 0$$

You cannot arbitrarily choose initial values for both your differential states ($x$, like molar inventories and temperatures) and your algebraic states ($y$, like flow rates and pressure drops). They must satisfy the algebraic constraints *and the time derivatives of those constraints* at exactly $t=0$.

When you feed an Excel sheet generated from a steady-state tool (like standard DWSIM or Aspen Plus) into your dynamic runner, that sheet only satisfies the static mass and energy balances ($f(x) = 0$). It does **not** contain or satisfy the dynamic hydraulic equations:

- It doesn't know the exact liquid crest height over the weirs ($l_{ow}$ via the Francis Weir formula).
- It doesn't know the precise vapor pipe resistance ($\Delta P$) between Stage 1 and the condenser drum.
- It doesn't know the sub-cooling thermal profile of the liquid sitting in the overhead line.

Because these values are missing or slightly off in the Excel sheet, the moment your dynamic solver evaluates the right-hand side (RHS) at $t=0$, it computes large, non-zero derivatives ($\dot{x} \neq 0$). The simulation experiences a **computational impulse shock**—which is exactly why Stage 4 exploded on restart, and why Stage 14 choked when you changed the drum volume.

### 3. What Commercial Software Does (That We Aren't Doing Yet)

When a commercial tool initializes dynamically, it does not let the integrator run immediately. Instead, it freezes time at $t=0$ and runs a completely separate mathematical solver (usually a structured Newton-Raphson or Levenberg-Marquardt root-finder) called a **Consistent Initializer**.

This initializer holds specified independent variables fixed (like the total feed rate and vessel geometries) and varies a targeted subset of initial states until **all derivatives ($\dot{x}$) across the entire matrix are simultaneously driven below a strict tolerance** (e.g., <1e-6 for normalized rates).

By modulating the un-converged boundary states (like the drum vapor packing and initial condenser duty) to force the step-zero derivatives to exactly zero, we will be executing the exact mathematical workflows that power industrial-grade dynamic simulators.

## Position

ChemSep steady-state results are valuable initialization data, but they are not a guaranteed dynamic initial condition for this model.

Use ChemSep/Excel values as a high-quality estimate for:
- components and thermo basis,
- approximate `T/P/x/y/L/V` profiles,
- product rates and duties,
- geometry and holdup scale.

The dynamic model must then convert that estimate into a state that is self-consistent with its own topology, holdup states, feed treatment, thermodynamics, and RHS equations.

## Why This Matters

An imported steady profile comes from another solver's mathematical topology. It can be perfectly steady in ChemSep and still be non-steady here if any of these differ:
- explicit reflux drum or bottom sump states,
- terminal condenser/reboiler interpretation,
- feed split basis,
- tray vapor holdup states,
- pressure/vapor-flow closure,
- energy states,
- thermo backend or binary parameters.

The recent C3/C4 diagnostic confirmed this. Freezing tray vapor derivatives allowed the steady-state detector to pass, but liquid compositions drifted far outside validation tolerance. That means numerical quiet is not the same thing as a valid initialized column.

The follow-up C3/C4 ChemSep warmer-feed audit added a second lesson: an exact source translation is not enough if the terminal equipment topology is assigned to the wrong dynamic state. The regenerated workbook matches the ChemSep `.sep` result block for duties, streams, profiles, and compositions, but full energy initialization still exposed total-condenser ownership problems when condenser duty was applied to a zero-liquid-holdup stage-1 energy state.

## Initialization Contract

The workbook supplies a seed. The runner/initializer is responsible for making that seed dynamic-ready.

Accepted uses of ChemSep results:
- source-topology material-balance parity when our topology is intentionally reduced to match ChemSep/source assumptions,
- initial guesses for a model-topology steady initializer,
- reference profiles for comparison after topology and thermo differences are reconciled.

Not accepted:
- treating raw ChemSep `L/V/x/y` as final truth for full dynamic runs with explicit vapor holdups and boundary vessels,
- forcing a run to pass by freezing or disabling physics that the validation claim depends on,
- accepting `steady_state_flag=1` without profile/conservation checks.

## Recommended Workflow

1. **Source Import**
   - Load ChemSep/Excel `T/P/x/y/L/V`, duties, products, geometry, and estimated holdups.
   - Preserve the original source profile for audit and comparison.

2. **Topology Reconciliation**
   - Convert terminal condenser/reboiler/source-stage assumptions into this model's explicit top drum, bottom sump, and reboiler mappings.
   - For total condensers, route overhead vapor condensation and condenser duty through the condenser/reflux-drum boundary model, not through a zero-holdup tray state.
   - Reconcile product draws and feed split assumptions before marching.

3. **Initialization Residual Audit**
   - Evaluate `column_rhs_v1.py` at `t=0`.
   - Report residuals by block: `tray_L`, `tray_V`, `top_L/top_V`, `bottom_L/bottom_V`, energy/temperature, pressure/vapor-flow, and feed-stage terms.
   - Use this to decide whether the remaining problem is structural or solvable.

4. **Sequential Dynamic-Consistency Solve**
   - Avoid a giant full-state Newton solve first.
   - Start with a narrow variable set, such as vapor compositions/holdups and boundary vessel states.
   - Add liquid composition, feed split, pressure/vapor-flow, and energy variables only when diagnostics prove they are needed.
   - Keep normalization, nonnegativity, and profile-deviation penalties explicit.

5. **Open-Loop Settle**
   - Run a short open-loop settle only after algebraic residuals are already small.
   - Controllers should be disabled until the plant model itself has a quiet baseline.

6. **Golden Seed Serialization**
   - Save accepted initialized states, thermo packets, hydraulic memory, and controller memory.
   - Use serialized seeds for disturbance and controller studies so every run starts from the same verified baseline.

## Acceptance Gates

An initialized state is accepted only if all relevant gates pass:
- low full-state derivatives by block, not just a low aggregate score,
- low `tray_V` residuals when vapor states are enabled,
- low `tray_L` residuals and no compensating liquid/vapor leakage,
- global and stage material closure,
- energy closure when energy states are enabled,
- total-condenser duty/energy closure at the condenser or reflux-drum boundary when a total condenser is present,
- pressure and vapor-flow diagnostics are physically reasonable,
- bounded drift from the intended source/seed profile,
- source/reference KPI comparison remains acceptable when the case is being used for validation.

`steady_state_flag=1` is useful diagnostic evidence. It is not sufficient by itself.

## Near-Term Implementation Plan

Use the C3/C4 case as the fast development case.

Implemented first tool:
- `tools/column_initialization_residual_audit.py`

The audit evaluates `column_rhs_v1.py` once at `t=0`, writes ranked state-rate residual rows, stage total phase-rate rows, and `summary.md`/`summary.json` outputs. It is now the first gate before accepting an imported workbook as a dynamic initial condition.

Initial audit evidence:
- C3/C4 parity with explicit vapor states fails immediately:
  - `logs/initialization_audits/c3c4_parity_noeq_preserveV_20260528/summary.md`
  - worst block: `tray_V`, stage 2, n-Butane, `0.0413 1/s` relative rate.
- C3/C4 source topology with vapor and boundary states disabled passes:
  - `logs/initialization_audits/c3c4_parity_noeq_noV_noBoundary_20260528/summary.md`
  - max relative rate `5.49e-05 1/s`, max tray total residual `0.0884 lbmol/h`.
- Gani source-topology ChemSep workbook passes to near roundoff:
  - `logs/initialization_audits/gani_source_topology_noV_noBoundary_20260528/summary.md`
  - max relative rate `3.26e-08 1/s`.
- Gani full workbook with explicit vapor states fails:
  - `logs/initialization_audits/gani_parity_noeq_preserveV_20260528/summary.md`
  - worst block: `tray_V`, stage 26, Isobutene, `0.0840 1/s` relative rate.

Recommended next tool:
- `tools/reconcile_column_vapor_closure_seed.py`

This first reconciliation tool has been added as an experimental local residual nudge. It updates tray vapor compositions from fixed-flow vapor residuals and can optionally update liquid compositions as well:
- `tools/reconcile_column_vapor_closure_seed.py`

Early C3/C4 local-nudge result:
- `logs/c3c4_splitter_openloop_seed_phaseclosure_blend025_20260528.xlsx`
- `logs/initialization_audits/c3c4_phaseclosure_blend025_20260528/summary.md`
- worst relative state rate improved from `0.0413 1/s` to `0.0369 1/s`, but the case still fails the initialization gate.

Boundary-aware coupled result:
- `logs/c3c4_splitter_openloop_seed_coupledclosure_blend010_iter3c_20260528.xlsx`
- `logs/initialization_audits/c3c4_coupledclosure_blend010_iter3c_20260528/summary.md`
- worst relative state rate improved from `0.0413 1/s` to `0.0284 1/s`.
- the dominant residual shifted from explicit `tray_V` stage 2 n-Butane to `tray_L` stage 2 n-Pentane.

Iterative coupled probe:
- driver: `tools/iterate_column_coupled_closure.py`
- first probe directory: `logs/c3c4_iterative_coupled_closure_20260531`
- best candidate found before timeout: `logs/c3c4_iterative_coupled_closure_20260531/c3c4_coupled_iter03_blend0.0781.xlsx`
- best audit: `logs/c3c4_iterative_coupled_closure_20260531/audit_iter03/summary.md`
- worst relative state rate improved to `0.0244 1/s`, but the case still fails.
- a smaller-step continuation from that best workbook worsened the residual, so the simple fixed-flow coupled iteration appears to stall above the initialization gate.

Bounded least-squares probe:
- tool: `tools/optimize_column_initialization_residual.py`
- probe workbook: `logs/c3c4_splitter_openloop_seed_lsq_stage2_18_19_20260531_r3.xlsx`
- audit: `logs/initialization_audits/c3c4_lsq_stage2_18_19_20260531_r3/summary.md`
- varying only selected tray liquid/vapor composition profiles improved the original seed to `0.0307 1/s`, but did not beat the best coupled-iteration result.

Spec/energy degree-of-freedom probes:
- spec-only boundary adjustment did not solve the defect:
  - `logs/initialization_audits/c3c4_initializer_specdof_trial1_20260531/summary.md`
  - worst relative rate stayed at `0.05312 1/s`.
- composition plus boundary specs improved material closure but did not pass:
  - `logs/initialization_audits/c3c4_initializer_specdof_comp_trial2_20260531/summary.md`
  - worst relative rate `0.03042 1/s`, max tray total material residual `31.67 lbmol/h`.
- direct feed vapor-fraction/no-flash handling shifted the dominant issue to feed-stage energy:
  - `logs/initialization_audits/c3c4_initializer_specdof_feedvf_trial5_noflash_20260531/summary.md`
  - worst state `tray_EL_BTU` stage 12, `0.02624 1/s`, about `6330 Btu/s`.
- adding energy residuals and bounded tray liquid-energy variables reduced the energy defect, but material closure became the limiter again:
  - `logs/initialization_audits/c3c4_initializer_specdof_energy_trial6a_noflash_20260531/summary.md`
  - worst state `tray_L` stage 2 n-Butane, `0.01819 1/s`, max tray total material residual `35.76 lbmol/h`.
- matching the ChemSep product specifications is now supported in the optimizer:
  - ChemSep specifies top reflux ratio `2.5` and bottom product flow `4761.98 lbmol/h`; distillate is not an independent fixed spec.
  - `tools/optimize_column_initialization_residual.py --chemsep-product-specs --reflux-ratio 2.5` varies distillate, enforces `reflux = 2.5 * distillate`, and keeps bottoms fixed.
  - probe audit: `logs/initialization_audits/c3c4_initializer_chemsep_specs_energy_trial7_noflash_20260531/summary.md`.
  - result: worst component residual stayed essentially unchanged (`0.01819 1/s`), but max tray total material residual improved to `14.84 lbmol/h`; source-equivalent degrees of freedom matter and should be preferred for this case.

Model-owned settle pilots:
- Starting from `logs/c3c4_initializer_chemsep_specs_energy_trial7_noflash_20260531.xlsx`, direct hydraulic pressure/vapor-energy settling with no pressure anchor is not acceptable:
  - `logs/column_summary_20260531_164508.csv`
  - the top pressure collapsed essentially to vacuum while the bottom remained near `232 psia`, and the final score worsened to `67.6`.
- Specified condenser duty alone slowed but did not fix the top-pressure collapse:
  - `logs/column_summary_20260531_164725.csv`
  - top pressure was still only about `12.65 psia` at `30 s`.
- A pressure-anchored hydraulic settle is the first directionally useful physical-settle path:
  - pilot: `logs/column_summary_20260531_164921.csv`
  - continuation: `logs/column_summary_20260531_165103.csv`
  - command form: `--runtime-mode hydraulic --condenser-duty-mode specified --enable-pressure-control --pressure-control-mv top-anchor --top-pressure-sp 218.439886`.
  - the score dropped from `12.65` at the end of the first `30 s` pilot to a best value of `5.90` about `35 s` into the continuation, with stage pressure held near the ChemSep source pressure.
  - the run did not settle; the score rose again to `9.93` by the end of the continuation, top-drum pressure was still far below the anchored top-stage pressure, and `K_state_over_K_thermo_max_abs` continued growing. Interpretation: pressure anchoring prevents the immediate hydraulic-pressure failure, but the top boundary/drum vapor state and top-end phase consistency still need a better initialization/closure before a golden seed can be accepted.
- Boundary-state seeding was added as the next diagnostic step:
  - tool: `tools/initialize_boundary_state_seed.py`
  - generated workbook: `logs/c3c4_initializer_chemsep_specs_energy_trial7_boundary_seed_20260531.xlsx`
  - the tool writes `Boundary State` from product stream compositions and explicit top/bottom holdups, and estimates the top vapor inventory from target pressure, temperature, vapor volume, and compressibility.
  - with an ideal-gas top-vapor estimate (`top_V = 75.85 lbmol`), the anchored `30 s` pilot `logs/column_summary_20260531_173542.csv` kept the top drum near `176 -> 185 psia` instead of near vacuum and improved the early score to `4.30` at `15 s`, but the case still failed and drifted to `7.08` by `30 s`.
  - with `Z=0.8` (`top_V = 94.81 lbmol`), the short pilot `logs/column_summary_20260531_173832.csv` kept the top drum near `208 -> 210 psia` through `15 s`, but the steady-state score was essentially unchanged. Interpretation: explicit top-drum vapor seeding is necessary to avoid the pressure-collapse artifact, but the remaining blocker is no longer simply missing top vapor inventory; material/energy closure still needs a model-owned initialization solve or an accepted pressure-boundary closure.
- A reflux-loop closure isolation diagnostic was added:
  - flag: `--debug-override-reflux-composition`
  - audit: `logs/initialization_audits/c3c4_initializer_chemsep_specs_energy_trial7_reflux_override_20260601/summary.md`
  - it forces the reflux composition entering stage 2 to match the condensed top vapor composition for one RHS evaluation.
  - result: the worst state moved from `tray_L` stage 2 n-Butane (`0.01819 1/s`) to `tray_L` stage 3 n-Butane (`0.01255 1/s`), while max tray total material residual stayed `14.84 lbmol/h`. Interpretation: reflux composition mismatch is a real contributor to the upper-tray hot spot, but not the whole initialization failure.
- Focused boundary-residual least-squares probes now support the same structure as the proposed external-advice objective:
  - tool: `tools/optimize_column_initialization_residual.py`
  - added knobs include `--residual-stages`, `--residual-top-boundary-only`, `--vary-top-liquid`, `--vary-top-vapor`, and `--vary-top-vapor-total`.
  - trial 2 workbook: `logs/c3c4_initializer_boundary_window_trial2_20260601.xlsx`
  - optimizer summary: `logs/c3c4_initializer_boundary_window_trial2_20260601.optimizer_summary.json`
  - audit: `logs/initialization_audits/c3c4_initializer_boundary_window_trial2_20260601/summary.md`
  - within the targeted stages 1-5, the in-process max relative residual dropped to `0.00553 1/s`; full-column audit then moved the dominant residual to the first untargeted stage, `tray_L` stage 6 n-Propane at `0.01880 1/s`.
  - max tray total material residual improved from `14.84 lbmol/h` in the boundary-seed baseline to `2.82 lbmol/h`, but the full initialization gate still failed. Interpretation: the boundary-residual formulation is useful and structurally pointed in the right direction, but a narrow local window can simply pass the component imbalance to the next tray. The next version needs either a wider simultaneous solve or an explicit interface/buffer residual at the edge of the optimized window.
- Dynamic boundary-clamping probes were added and tested as a simpler physical-settle alternative:
  - RHS/CLI flag: `--debug-clamp-top-drum-pressure-psia`
  - paired with existing `--debug-override-reflux-composition`
  - the pressure clamp overrides the computed top-drum pressure used by hydraulic boundary logic and also acts as the hydraulic top anchor during the diagnostic settle.
  - 200 s clamped settle: `logs/column_summary_20260601_103656.csv`; the run improved early but did not flatten and ended with `steady_state_score=17.37`, `ss_max_rel_state_rate_per_s=0.0441/s`.
  - 40 s clamped restart audit: `logs/initialization_audits/c3c4_clamped_boundary_settle_40s_restart_unclamped_20260601/summary.md`; unclamped gate failed with max relative rate `0.0703/s`.
  - 40 s clamped settle with specified condenser duty: `logs/column_summary_20260601_104755.csv`; the unclamped restart audit `logs/initialization_audits/c3c4_clamped_boundary_settle_40s_speccond_restart_unclamped_20260601/summary.md` also failed at `0.0702/s`.
  - Interpretation: boundary clamping is useful as a diagnostic and prevents simple pressure collapse, but it is not sufficient as a golden-seed generator for this case. The clamped state still carries energy/vapor residuals that reappear immediately when audited without clamps.
- Thermal-volumetric optimizer probes were added after the clamped-settle result:
  - `tools/optimize_column_initialization_residual.py` now supports `--vary-condenser-duty`, `--condenser-duty-mode`, and `--condenser-duty-btuph`.
  - the optimizer can now vary tray vapor-energy states even when the seed `tray_EV_BTU` is zero, using `--energy-denom-floor-btu` as the absolute scale.
  - top-four vapor-flow/EL-only trial: `logs/c3c4_initializer_thermal_vapor_top4_trial1_20260601.xlsx`, audit `logs/initialization_audits/c3c4_initializer_thermal_vapor_top4_trial1_20260601/summary.md`, failed at `0.03455/s`, dominated by `tray_V` stage 2 n-Butane.
  - top-four vapor-composition/flow/EL trial: `logs/c3c4_initializer_thermal_vapor_top4_trial2_comp_20260601.xlsx`, audit `logs/initialization_audits/c3c4_initializer_thermal_vapor_top4_trial2_comp_20260601/summary.md`, failed at `0.03332/s`, dominated by `tray_V` stage 2 n-Propane.
  - top-four vapor-composition/flow/EL/EV/condenser-duty trial: `logs/c3c4_initializer_thermal_vapor_top4_trial3_q_ev_20260601.xlsx`, audit `logs/initialization_audits/c3c4_initializer_thermal_vapor_top4_trial3_q_ev_20260601/summary.md`, failed at `0.03308/s`, still dominated by `tray_V` stage 2 n-Propane. Condenser duty moved by about `5.46%`; top vapor total moved by about `23.9%`; EV residual was no longer limiting.
  - Interpretation: the thermal-volumetric degrees of freedom are real and improve the clamped-restart residual, but the top-four problem is not the whole problem. Stage-2 vapor closure remains coupled to the rest of the vapor traffic/pressure/energy network, and the full audit still shows large vapor residuals outside the optimized window. Do not treat upper-four thermal optimization as a final initializer.
- The optimizer now supports explicit residual block selection with `--residual-state-blocks` and `--residual-energy-blocks`.
  - global vapor plus liquid-enthalpy probe: `logs/c3c4_initializer_global_vapor_el_trial1_20260601.xlsx`, summary `logs/c3c4_initializer_global_vapor_el_trial1_20260601.optimizer_summary.json`, audit `logs/initialization_audits/c3c4_initializer_global_vapor_el_trial1_20260601/summary.md`.
  - objective: all stages, residual blocks `tray_V` and `tray_EL_BTU`; free variables were vapor traffic, tray energy states, condenser duty, and ChemSep-style distillate/reflux ratio.
  - result: the optimizer reduced its internal objective but the audit failed at `0.04837/s`, dominated by `tray_V` stage 2 n-Butane, with max tray total material residual `5255 lbmol/h`.
  - Interpretation: global vapor-flow and liquid-energy adjustment without composition/profile degrees of freedom is not an adequate initializer. It can reduce a narrow objective while worsening the full dynamic seed. The next useful probe must either include global vapor/liquid composition variables with strong conservation regularization, or move from profile tweaking to a formal pressure/vapor-flow closure equation.
- A formal pressure-flow closure wrapper was added around the existing DAE pilot residual:
  - tool: `tools/solve_pressure_flow_closure.py`
  - probe workbook: `logs/c3c4_initializer_pf_closure_trial1_20260601.xlsx`
  - summary: `logs/c3c4_initializer_pf_closure_trial1_20260601.pf_closure_summary.json`
  - audit: `logs/initialization_audits/c3c4_initializer_pf_closure_trial1_20260601/summary.md`
  - result: the PF algebraic residual closed tightly (`P_inf=0.116 psia`, `V_inf=1.80 lbmol/h`) after bounded pressure and vapor-flow adjustment, but the full dynamic audit failed worse at `0.06832/s`, dominated by `tray_V` stage 2 n-Butane, with max tray total material residual `7943 lbmol/h`.
  - Interpretation: pressure/flow closure alone is not an accepted initializer when explicit tray vapor inventories are preserved from the seed. The solved P/V profile must be accompanied by compatible vapor holdup, vapor composition, and vapor/energy state reconciliation; otherwise the workbook can be algebraically quiet in P/V while dynamically inconsistent in component vapor inventory.
- PF closure now includes a default-on vapor-state synchronization step:
  - implementation: `tools/solve_pressure_flow_closure.py` back-calculates `Vapor Holdup (lbmol)` from the solved pressure profile using the same `PV=nZRT` basis used by runner startup seeding, and updates `Tray EV (BTU)` from synced vapor holdup and vapor enthalpy when energy states are present.
  - sync can be disabled with `--no-sync-vapor-state` to reproduce the PF-only diagnostic.
  - synced probe workbook: `logs/c3c4_initializer_pf_closure_trial2_syncV_20260601.xlsx`
  - summary: `logs/c3c4_initializer_pf_closure_trial2_syncV_20260601.pf_closure_summary.json`
  - audit: `logs/initialization_audits/c3c4_initializer_pf_closure_trial2_syncV_20260601/summary.md`
  - result: PF residuals stayed tight (`P_inf=0.116 psia`, `V_inf=1.80 lbmol/h`), while the full audit improved from the PF-only `0.06832/s` to `0.02447/s`; max tray total material residual fell from `7943` to `2572 lbmol/h`, and the dominant `tray_V` residual moved from stage 2 n-Butane to stage 18 n-Propane.
  - Interpretation: synchronizing explicit vapor density is essential and materially helpful. It still does not close the initialization gate because vapor composition/material closure and stage-2 liquid-energy closure remain inconsistent. The next PF-based initializer should add bounded vapor-composition and liquid-energy reconciliation on top of the synchronized P/V/MV/EV seed.
- A Pass 2 terminal-layer optimization was tested on the synchronized PF seed:
  - narrow terminal-window trial: `logs/c3c4_initializer_pf_pass2_terminal_layers_trial1_20260601.xlsx`, summary `logs/c3c4_initializer_pf_pass2_terminal_layers_trial1_20260601.optimizer_summary.json`, audit `logs/initialization_audits/c3c4_initializer_pf_pass2_terminal_layers_trial1_20260601/summary.md`.
  - objective: stages `1-3,18-20`, residual blocks `tray_L`, `tray_V`, and `tray_EL_BTU`; free variables were local liquid/vapor compositions, tray energy states, and a small boilup adjustment with profile regularization back to the synchronized PF seed.
  - result: the in-process targeted objective improved to `0.02198/s`, but the full audit worsened to `0.04077/s`; the dominant residual moved just outside the bottom window to `tray_V` stage 17 n-Propane.
  - buffered terminal-window trial: `logs/c3c4_initializer_pf_pass2_terminal_layers_trial2_buffer_20260601.xlsx`, summary `logs/c3c4_initializer_pf_pass2_terminal_layers_trial2_buffer_20260601.optimizer_summary.json`, audit `logs/initialization_audits/c3c4_initializer_pf_pass2_terminal_layers_trial2_buffer_20260601/summary.md`.
  - result: the widened window `1-4,15-20` still worsened the full audit to `0.03650/s`; the dominant residual moved inward again to `tray_V` stage 14 n-Propane.
  - Interpretation: localized terminal-layer composition/EL fitting can reduce its own window objective, but it acts like a moving shear plane and transfers the vapor component imbalance into the first untargeted interior stages. Do not continue by simply widening local windows. The next formulation should include a global vapor-component conservation residual, explicit interface residuals, or a simultaneous PF/MV/EV/composition solve with whole-column regularization.
- A conservative whole-column composition/energy fit was tested from the synchronized PF seed:
  - workbook: `logs/c3c4_initializer_pf_global_conserved_trial1_20260601.xlsx`
  - summary: `logs/c3c4_initializer_pf_global_conserved_trial1_20260601.optimizer_summary.json`
  - audit: `logs/initialization_audits/c3c4_initializer_pf_global_conserved_trial1_20260601/summary.md`
  - objective: all stages, residual blocks `tray_L`, `tray_V`, and `tray_EL_BTU`; free variables were all liquid/vapor compositions, all tray energy states, condenser duty, and a small boilup adjustment, with tight profile bounds and a high `--tray-total-penalty 80`.
  - result: the full audit improved modestly from the synchronized PF baseline `0.02447/s` to `0.02253/s`, with max tray total material residual essentially unchanged (`2570 lbmol/h`). Unlike the terminal-window fits, the residual did not create a new moving interface; the dominant residual returned to `tray_V` stage 2 n-Propane.
  - Interpretation: global conservation regularization is the safer direction, but independent tray-by-tray composition variables with penalties are too blunt and high-dimensional. The next version should reduce the variable space to smooth whole-column profile coefficients or splines, and should include explicit global/stage total material residuals in the primary objective rather than relying only on a penalty term.
- A smooth coefficient-profile fit was tested from the synchronized PF seed:
  - tool: `tools/optimize_column_profile_coefficients.py`
  - workbook: `logs/c3c4_initializer_profile_coeff_trial1_20260601.xlsx`
  - summary: `logs/c3c4_initializer_profile_coeff_trial1_20260601.profile_coeff_summary.json`
  - audit: `logs/initialization_audits/c3c4_initializer_profile_coeff_trial1_20260601/summary.md`
  - objective: low-order smooth whole-column corrections to tray temperature, liquid composition logits, vapor composition logits, liquid energy, boilup, and condenser duty; residuals included total liquid/vapor/stage material terms, component terms, tray liquid energy, and coefficient regularization.
  - result: the full audit improved only slightly from the synchronized PF baseline `0.02447/s` to `0.02381/s`; max tray total material residual improved from `2572` to `2504 lbmol/h`, but the gate still failed and the dominant residual stayed in `tray_V` stage 18 n-Propane.
  - Interpretation: smooth global profile corrections are better behaved than local terminal-window fitting, but they still do not supply the missing closure. The remaining defect is not merely noisy profile data; it is a coupled vapor-component/transport consistency problem that likely needs the initializer to solve for the vapor inventories/compositions and traffic together, or to run a true dynamic steady-state solve with those variables free.

ChemSep warmer-feed source-workbook cleanup:
- source workbook: `logs/c3c4_depropanizer_chemsep_warmer_feed_pr76_source_20260531.xlsx`
- source parity audit: `logs/chemsep_warmer_feed_source_parity_audit_20260531/chemsep_warmer_feed_parity_audit.md`
- energy-seed reconciler: `tools/reconcile_column_energy_seed.py`
- energy-reconciled workbook: `logs/c3c4_depropanizer_chemsep_warmer_feed_pr76_source_energy_reconciled_20260531.xlsx`
- result: exact ChemSep translation plus model-consistent energy seed reduces the dominant profile-flow energy residual, but remaining full-topology work is blocked by phase closure and by total-condenser energy ownership (`DD-033`).

Conclusion: local nudging is diagnostic, and damped coupled closure is directionally useful, but still not sufficient as a standalone initializer. The bounded optimizer confirms that selected composition degrees of freedom alone do not close the full explicit-vapor topology. Adding boundary specs, feed split, and energy states moves the dominant defect in physically interpretable ways, which validates the degrees-of-freedom approach, but it still does not produce an accepted initialized state. The next initializer should solve a tighter simultaneous material/energy/profile-flow closure problem with stronger material-balance and window-interface constraints before falling back to physical settle/golden-seed serialization. Only after the residual audit and profile/KPI gates pass should the state be serialized as a golden seed.

Hybrid startup pivot:
- The optimizer/profile-nudging path is now considered diagnostic rather than the primary initialization strategy.
- Runner/RHS support a `total-reflux` runtime mode for closed-column startup:
  - feed, distillate, and bottoms external mass exchange are suppressed in the RHS,
  - hydraulic pressure and energy vapor-flow behavior follow hydraulic-mode defaults,
  - overhead vapor condensation is recycled as reflux; before vapor reaches the condenser, the mode uses the nominal seed reflux as a kick-start circulation flow.
  - optional startup controls:
    - `--total-reflux-startup-ramp-tau-sec` applies a first-order ramp to active boilup/reboiler duty in total-reflux mode,
    - `--total-reflux-startup-min-ramp-fraction` sets the initial active fraction during that ramp,
    - `--debug-clamp-top-drum-pressure-duration-sec` automatically releases the diagnostic top-drum pressure clamp after the specified Phase 1 duration.
- Smoke test:
  - command seed: `logs/c3c4_initializer_profile_coeff_trial1_20260601.xlsx`
  - run: `logs/column_summary_20260601_152940.csv`
  - result: the model executed without choking for `10 s` at `dt=0.2 s`, but did not settle; final `steady_state_score=18.60`, `ss_max_rel_state_rate_per_s=0.0516/s`, dominated by `tray_V` stage 2 n-Butane, with `ss_max_temp_rate_F_per_s=2.79`.
  - interpretation: the hybrid startup mode is mechanically viable, but a useful startup recipe still needs staged ramping/damping. Simply switching to total reflux from the current seed exposes fast vapor/thermal transients rather than producing a golden seed immediately.
- Ramped smoke note:
  - after adding ramp/clamp-duration controls, the first verification attempt exposed high startup-conditioning cost with full Clapeyron PR tracing; it timed out before writing a complete summary.
  - `--fast-startup` alone skips the fresh-startup thermo conditioning, but explicit restart workbooks can still enter the hidden restart re-entry settling path. For total-reflux startup recipe trials from a reconciled/restart-style workbook, use `--fast-startup --disable-restart-reentry-settling` unless the purpose of the run is to test restart re-entry behavior.
  - fast/no-reentry verification run: `logs/column_summary_20260601_155641.csv`.
    - command seed: `logs/c3c4_initializer_profile_coeff_trial1_20260601.xlsx`
    - recipe knobs: `--runtime-mode total-reflux --fast-startup --disable-restart-reentry-settling --total-reflux-startup-ramp-tau-sec 10 --total-reflux-startup-min-ramp-fraction 0.2 --debug-clamp-top-drum-pressure-psia 222.62 --debug-clamp-top-drum-pressure-duration-sec 30`
    - result: completed a `1 s` wiring check in about `69 s` wall time. Total-reflux mode was active, the pressure clamp held `P_top_drum_psia=222.62`, the startup ramp factor was `0.276`, realized boilup was `2217 lbmol/h`, and recycled reflux was `8630 lbmol/h`.
    - interpretation: this is not a settling result; the final score remained high (`steady_state_score=50.94`, worst `tray_V` stage 19 n-Butane, `ss_max_temp_rate_F_per_s=7.64`). The useful conclusion is that the runtime controls are wired and the expensive restart-conditioning path can be bypassed for recipe development.
  - 10 s bench run: `logs/column_summary_20260601_160255.csv`.
    - result: completed in about `131 s` wall time, so the 1 s run's `69 s` cost is not purely per-sim-second integration cost.
    - final `t=10 s` metrics: `steady_state_score=27.31`, `ss_max_rel_state_rate_per_s=0.0641/s`, worst state `tray_L` stage 12 n-Pentane, `ss_max_temp_rate_F_per_s=4.10`, startup factor `0.706`, realized boilup `5667 lbmol/h`, recycled reflux `10703 lbmol/h`, top pressure held at `222.62 psia`.
    - interpretation: the early stage-19 vapor transient eased and the visible bottleneck moved to the feed-stage liquid inventory/energy neighborhood. That is a more useful startup-dynamics signal than the 1 s wiring check, but it is still not a settled or accepted seed.
  - 60 s ramp/clamp-release run: `logs/column_summary_20260601_160658.csv`.
    - recipe: `--total-reflux-startup-ramp-tau-sec 15`, pressure clamp at `222.62 psia` released after `25 s`.
    - result: completed in about `82 s` wall time. The score initially improved, then the stage-12 liquid residual spiked before/near clamp release (`steady_state_score=345.90` at `25 s`). After release the top drum pressure fell to the raw model pressure of about `171.26 psia` and the score parked at `66.67`, dominated by the temperature-rate criterion (`ss_max_temp_rate_F_per_s=10.0` with tolerance `0.15`).
  - 60 s held-clamp comparison: `logs/column_summary_20260601_160912.csv`.
    - result: also completed in about `82 s`; holding the pressure clamp through the window did not prevent the same score plateau. The top-drum raw pressure stayed near `171.26 psia` even while the reported/clamped pressure stayed `222.62 psia`, and the temperature-rate criterion remained pegged. `K_state_over_K_thermo_max_abs` grew from `15.7` at `10 s` to about `4014` by `60 s`.
    - interpretation: the 60 s recipe is not a golden-seed candidate. It confirms that total-reflux startup can be marched cheaply enough for recipe development, but this particular closed-column/ramped-boilup/no-equilibrium recipe drives energy/K-state consistency away from the thermo manifold after the feed-zone transient. Do not simply extend this recipe to 300 s without changing the startup physics or diagnostics.
  - Equilibrium-relaxation follow-up:
    - The code already contains runtime equilibrium-relaxation modes, so no new K-state ODE was added.
    - Composition-only relaxation probe: `logs/column_summary_20260601_161315.csv` (`10 s`) and `logs/column_summary_20260601_161453.csv` (`60 s`), using `--equilibrium-relaxation-mode composition-only --equilibrium-tau-sec 0.5`.
      - At `10 s`, this improved K consistency materially versus no-equilibrium (`K_state_over_K_thermo_max_abs=1.85` instead of about `15.7`) and slightly improved the score (`24.02` versus `27.31`), but the `60 s` run worsened badly (`steady_state_score=606.98`, worst `tray_V` stage 13 n-Butane, temperature rate pegged).
    - Guarded phase-holdup relaxation probe: `logs/column_summary_20260601_161642.csv`, using `--equilibrium-relaxation-mode phase-holdup --equilibrium-tau-sec 2.0 --equilibrium-phase-holdup-guard-lbmol 1.0 --equilibrium-energy-damping-gain 0.1`.
      - This kept K consistency in the same rough range at `10 s` (`K_state_over_K_thermo_max_abs=1.94`) but made the inventory residual worse (`steady_state_score=42.35`), dominated by `tray_V` stage 18 n-Butane.
    - interpretation: thermodynamic grounding is necessary, but the existing relaxation paths do not by themselves produce a stable total-reflux startup recipe. Composition-only helps K coherence but lacks enough energy/latent closure; phase-holdup relaxation introduces stronger phase-inventory shocks. The next recipe change should be more targeted than simply "turn equilibrium back on": reduce the reflux/boilup shock, improve top-boundary pressure/energy consistency, and/or stage equilibrium relaxation gradually instead of applying one fixed tau from `t=0`.
  - Staged relaxation and coordinated reflux/boilup probes:
    - The runner/RHS now expose `--equilibrium-tau-ramp-initial-sec`, `--equilibrium-tau-ramp-final-sec`, `--equilibrium-tau-ramp-decay-sec`, and `--total-reflux-scale-reflux-with-startup-factor`.
    - Ramped-tau plus reflux-scaling `10 s` probe: `logs/column_summary_20260601_164412.csv`.
      - recipe: composition-only equilibrium relaxation with tau ramp `10 -> 0.5 s` over `40 s`, reflux scaled by the total-reflux startup factor.
      - result: reflux/boilup traffic was better coordinated, but the tau ramp was too loose at `10 s` (`eq_relax_tau_effective_sec=7.90`), so K drift stayed high (`K_state_over_K_thermo_max_abs=10.60`) and the score was worse than fixed-tau composition-only (`29.74`).
    - Fixed-tau plus reflux-scaling `10 s` probe: `logs/column_summary_20260601_164630.csv`.
      - recipe: composition-only equilibrium relaxation with `--equilibrium-tau-sec 0.5`, reflux scaled by the startup factor.
      - result: best short-window recipe so far. Final `10 s` score `22.49`, `K_state_over_K_thermo_max_abs=1.85`, `ss_max_temp_rate_F_per_s=2.24`, realized boilup `4732 lbmol/h`, returned reflux `4214 lbmol/h` from available condensate `7152 lbmol/h`.
    - Fixed-tau plus reflux-scaling `60 s` probe: `logs/column_summary_20260601_164845.csv`.
      - result: the short-window improvement did not persist. K coherence remained far better than the no-equilibrium run (`K_state_over_K_thermo_max_abs=2.39` at `60 s`), but the feed-stage liquid residual became severe (`steady_state_score=286.43`, worst `tray_L` stage 12 n-Butane) and the temperature-rate criterion pegged again.
      - interpretation: coordinated reflux/boilup and composition relaxation are helpful but not sufficient. They reduce the top/lower traffic shock and prevent catastrophic K drift, yet stage 12 energy/material initialization remains incompatible with the total-reflux no-feed trajectory. Next probes should focus on feed-stage energy/composition reinitialization or a gentler feed-zone washout sequence, not simply longer runtime.
  - Feed-stage smoothing probes:
    - Added opt-in preconditioner: `tools/precondition_feed_stage_total_reflux_seed.py`.
    - The tool smooths the selected feed-stage liquid composition and temperature by default; liquid holdup and energy smoothing are available only with explicit `--smooth-holdup` / `--smooth-energy` because the first aggressive test was destabilizing.
    - Aggressive stage-12 x/T/ML/EL smoothing workbook: `logs/c3c4_initializer_profile_coeff_trial1_feed12_smooth_20260601.xlsx`.
      - summary: `logs/c3c4_initializer_profile_coeff_trial1_feed12_smooth_20260601.summary.json`.
      - result: worsened the `60 s` recipe (`logs/column_summary_20260601_202456.csv`), ending at `steady_state_score=504.14`, worst `tray_V` stage 14 n-Butane, with `ss_max_temp_rate_F_per_s=53.54`.
    - Gentler stage-12 x/T-only smoothing workbook: `logs/c3c4_initializer_profile_coeff_trial1_feed12_smooth_xTonly_20260601.xlsx`.
      - summary: `logs/c3c4_initializer_profile_coeff_trial1_feed12_smooth_xTonly_20260601.summary.json`.
      - result: very small short-window improvement (`22.29` at `10 s` versus `22.49` baseline), but the `60 s` recipe still failed (`logs/column_summary_20260601_202718.csv`) at `steady_state_score=296.50`, worst `tray_L` stage 12 n-Butane.
    - interpretation: single-stage feed-bulge smoothing does not solve the total-reflux startup blocker. It confirms stage 12 is the visible failure location, but simply erasing the local composition/temperature cliff or re-anchoring one stage's holdup/energy does not supply the missing coupled material/energy trajectory. Avoid widening this manually stage-by-stage without a stronger conservation objective.
  - Continuous-to-total-reflux boundary ramp probes:
    - The RHS/runner now support `--total-reflux-boundary-ramp-duration-sec`. In `total-reflux` mode, this starts with workbook feed/product boundaries active and linearly scales feed, distillate, and bottoms to zero while blending reflux from nominal workbook reflux toward full condensate return. If omitted, total-reflux mode keeps the previous immediate seal behavior.
    - 60 s boundary ramp: `logs/column_summary_20260601_203735.csv`.
      - recipe: composition-only equilibrium relaxation with `tau=0.5 s`, no startup boilup/reflux ramp, pressure clamp released after `25 s`, boundary ramp duration `60 s`.
      - result: materially improved the first half of the run (`steady_state_score=5.25` at `5 s`, `13.07` at `25 s`), but failed as the boundary seal completed; final score `295.76`, worst `tray_V` stage 13 n-Butane, temperature rate pegged, K ratio still reasonable at `1.95`.
    - 120 s boundary ramp: `logs/column_summary_20260601_204003.csv`.
      - result: early behavior again improved (`5.31` at `10 s`, `19.93` at `30 s`), but the trajectory degraded as external boundaries approached zero and failed after full closure; final score `541.84`, worst `tray_V` stage 13 n-Butane, temperature rate pegged, K ratio `2.63`.
    - interpretation: the reverse-startup ramp is the best diagnostic recipe so far for the early transient, proving the immediate total-reflux switch was part of the problem. It still does not produce an accepted sealed total-reflux seed. The remaining failure is no longer global K de-coherence or a single feed-stage cliff; the fully sealed target appears incompatible with the current explicit-vapor/energy/top-boundary state unless additional pressure/energy/product-boundary degrees of freedom are kept active or solved algebraically.
  - Continuous open-loop pivot:
    - Unanchored continuous hydraulic run: `logs/column_summary_20260601_204815.csv`.
      - recipe: `--runtime-mode hydraulic`, continuous feed/products active, composition-only equilibrium relaxation with `tau=0.5 s`, no feed flash, preserved Excel vapor holdup.
      - result: continuous boundaries helped temporarily, but the run still drifted into the familiar stage-13 vapor/temperature failure by `90 s` (`steady_state_score=409.05`, worst `tray_V` stage 13 n-Butane, top-drum pressure near `172.26 psia`).
    - Top-pressure-anchored continuous hydraulic run: `logs/column_summary_20260601_205129.csv`.
      - recipe: same as above, with diagnostic top-drum pressure clamp at `222.62 psia` for the visible window.
      - result: strongest initialization behavior to date. Scores stayed near `2-3` for most of the run (`3.46` at `10 s`, `1.63` at `60 s`, `1.96` at `90 s`), with temperature rates generally below `0.6 F/s` except for a bounded bump.
      - caveat: the final `90 s` row released the clamp due to floating-point time slightly exceeding the clamp duration, so it was repeated with a longer clamp.
    - Top-pressure-anchored continuous hydraulic 120 s run: `logs/column_summary_20260601_205429.csv`.
      - result: remained stable enough for development but did not pass the steady-state gate. Scores: `3.46` at `10 s`, `1.63` at `60 s`, `1.96` at `90 s`, `8.21` at `120 s`; final worst state `tray_V` stage 18 n-Pentane, final `ss_max_temp_rate_F_per_s=1.23`, K ratio `3.16`.
      - interpretation: the practical initialization path should pivot away from sealed total reflux and toward a continuous operating baseline with explicit top-pressure/energy boundary ownership. The top-pressure anchor is not merely cosmetic; without it the top drum raw pressure falls near `172 psia` and the stage-13 failure returns. Next work should convert the diagnostic pressure anchor into an accepted boundary condition/controller/initializer, then serialize a continuous golden seed once the residual gate is tightened.
    - Existing pressure-control comparison:
      - Condenser-duty PI already exists in the runner (`--enable-pressure-control --pressure-control-mv condenser-duty`), so no duplicate PI loop was added to `column_rhs_v1.py`.
      - Coupled total-condense PI probe: `logs/column_summary_20260601_210005.csv`.
        - result: did not replace the pressure anchor. Final pressure was still low (`P_top_drum_psia=214.08 psia`), final score `169.64`, worst `tray_V` stage 10 n-Propane.
      - Specified-duty PI probe: `logs/column_summary_20260601_210332.csv`.
        - result: cleaner duty authority and better final score than coupled total-condense, but still oscillatory and not accepted. Final `P_top_drum_psia=216.34 psia`, final score `12.18`, worst `tray_L` stage 12 n-Pentane.
      - Top-anchor pressure-control probe: `logs/column_summary_20260601_210550.csv`.
        - recipe: `--enable-pressure-control --pressure-control-mv top-anchor --top-pressure-sp 222.62 --top-pressure-anchor-min 222.62 --top-pressure-anchor-max 222.62`.
        - result: reproduced the diagnostic pressure-anchor behavior without using the debug clamp. Scores matched the anchored baseline closely (`1.63` at `60 s`, `8.21` at `120 s`).
      - 200 s top-anchor extension: `logs/column_summary_20260601_211349.csv`.
        - result: the residual did not monotonically clear. Scores were `1.63` at `60 s`, `1.96` at `90 s`, `8.21` at `120 s`, and `6.85` at `200 s`; late behavior was dominated by lower-column `tray_V` n-Pentane and temperature-rate residuals.
      - serialization gate:
        - clean 60 s freeze: `logs/column_summary_20260601_211851.csv`, restart workbook `logs/c3c4_initializer_profile_coeff_trial1_20260601__restart_20260601_211851.xlsx`.
        - immediate 10 s restart from that workbook: `logs/column_summary_20260601_212055.csv`.
        - result: the restarted run survived numerically but did not preserve the low-residual state. Score spiked to `135.56` at `2 s`, `72.20` at `4 s`, `35.68` at `6 s`, `187.21` at `8 s`, then relaxed to `4.58` at `10 s`, initially dominated by `tray_V` stage 4 n-Butane.
      - top-drum pressure-charge probe:
        - the `60 s` anchored checkpoint had `P_top_drum_psia=171.94`, `MV_top_drum_lbmol=75.85`, and `V_top_drum_vapor_ft3=2192`; matching `222.62 psia` at the same state would require about `1.295x` more vapor inventory or about `1693 ft3` headspace.
        - `--top-drum-vapor-volume-ft3 1693.107` was not the effective runtime lever when total drum volume is active; the RHS recomputes vapor headspace from total vessel volume minus liquid volume. The run `logs/column_summary_20260601_212549.csv` therefore matched the base specified-duty PI behavior.
        - applying the intended physical lever with `--top-drum-total-volume-ft3 3831.06` (`logs/column_summary_20260601_212839.csv`) raised raw pressure to the target neighborhood (`224.82 psia` at `120 s`) but worsened the residual to `88.89`, dominated by feed-zone/lower-column component transport.
      - interpretation: Pattern 1 (condenser-duty PI) is architecturally present but not yet tuned/authoritative enough for this initialization case. Pattern 2 as a pressure anchor is supported through the pressure-control MV path and remains useful diagnostically, but it is not an accepted physical initializer while raw `P_top_drum_psia` remains near `172-174 psia`. The `60 s` top-anchor row is the best low-residual checkpoint observed so far, but it is not a certified steady state and workbook restart serialization is not clean enough to make it a golden seed. Keep the distinction clear that `P_top_psia` is anchored while raw `P_top_drum_psia` remains low. A true golden seed likely needs native state serialization or closure of the missing condenser/top-boundary pressure physics, not another Excel restart loop.
      - additional interpretation: matching raw drum pressure by headspace sizing alone is not sufficient. It confirms the pressure deficit is real, but the missing closure is coupled: pressure, condenser duty, overhead vapor admission, reflux/product traffic, and stage composition/energy transport must be solved consistently.
      - condenser duty matching probe:
        - implementation: runner flag `--init-match-condenser-duty`, which evaluates the live total-condenser duty requirement once at `t=0` and uses that as the initial condenser-duty bias.
        - probe: `logs/column_summary_20260601_214021.csv` with coupled total-condense condenser-duty PI.
        - result: the flag applied a matched duty of `-5.009e7 Btu/h` at the `222.62 psia` target pressure, but the live unanchored run still operated from the raw top-drum pressure path (`P_top_drum_psia` rose only from about `171.7` to `182.4 psia` over `30 s`). The pressure gate stayed half-open (`V_to_top_drum_pressure_gate_scale=0.5`), and the final score was `13.17`, essentially the same class as the earlier specified-duty PI behavior.
        - interpretation: scalar duty matching is a useful diagnostic but not the missing closure. Matching duty at the target pressure does not by itself make the reflux drum pressure, overhead vapor admission, and condenser split physically consistent on the first live step.
      - top-drum vapor packing plus duty matching probe:
        - implementation: runner flag `--init-pack-top-drum-vapor-to-pressure`, with optional `--init-top-drum-vapor-pressure-psia`, scales only the explicit `top_V` inventory so the raw reflux-drum pressure starts near the pressure target. It can be combined with `--init-match-condenser-duty`.
        - corrected short probe: `logs/column_summary_20260602_083648.csv`.
        - corrected `30 s` probe: `logs/column_summary_20260602_083924.csv`.
        - result: the pack increased top vapor inventory from `75.85` to `105.37 lbmol` (`scale=1.389`), lifting the raw top-drum pressure from `171.26` to about `218.20 psia` before marching. The `30 s` coupled total-condense condenser-duty PI run ended with score `2.35`, max relative state rate `0.00463/s`, and temperature rate `0.352 F/s`; pressure stayed near `218.2-218.9 psia`. This is much better than duty matching alone (`13.17` at `30 s`) and far better than the earlier coupled total-condense PI run (`169.64`), but it still fails the steady-state gate.
        - interpretation: the pasted "primordial vapor charge" idea is materially useful when applied to explicit `top_V`, and it confirms the top-drum vapor inventory deficit was a real part of the closure failure. It is still not sufficient by itself: the pressure gate remains at `0.5` because the stage/drum pressure relation lands at the soft-gate midpoint, and the residual migrates to stage-2 material transport and temperature-rate criteria. Next work should tune/solve the coupled top-boundary target more formally rather than adding unrelated profile tweaks.
      - pressure-gate isolation probe:
        - the gate function is explicitly in psia and returns `0.5` by construction at zero driving force, so the observed midpoint is not a units bug.
        - gate-disabled comparison: `logs/column_summary_20260602_084909.csv`, using the same packed/duty-matched `30 s` recipe plus `--disable-top-drum-pressure-gate`.
        - result: disabling the gate increased live vapor slip to the reflux drum (`125.20 lbmol/h` vs `68.07 lbmol/h`) and removed the blocked-slip term, but the final score stayed essentially unchanged (`2.35`), with the same dominant `tray_L` stage-2 n-Butane residual and about the same temperature-rate criterion (`0.352 F/s`).
        - additional target test: lowering the pack target to `218.5 psia` (`logs/column_summary_20260602_084509.csv`) also did not improve the case (`score=2.41`).
        - interpretation: do not spend the next pass merely tuning `--top-drum-pressure-gate-soft-psi`. The gate telemetry is useful, but the immediate blocker is the top-boundary state relation and the surviving upper-liquid/energy residual after the vapor slip choke is removed.
      - reflux-flow isolation probe:
        - code trace: stage-2 reflux composition is dynamic (`x_in[1]=x_topL`) when explicit top boundary states are present, but the reflux flow is still the boundary/controller value outside total-reflux mode.
        - probe: `logs/column_summary_20260602_090810.csv`, using the same packed/duty-matched recipe plus `--reflux 5701.145898904781` to match the seed's stage-2 liquid outlet instead of the ChemSep reflux ratio value (`5967.32 lbmol/h`).
        - result: final score improved from `2.35` to `1.43`; the temperature-rate criterion dropped from `0.352 F/s` to `0.135 F/s`, below the current `0.15 F/s` tolerance. Stage-2 total liquid accumulation was eliminated.
        - remaining problem: the residual moved down the liquid profile. Stage 3 then accumulated about `0.0631 lbmol/s`, matching the liquid traffic step from stage 2 (`5701.15 lbmol/h`) to stage 3 (`5473.93 lbmol/h`).
        - interpretation: reflux-flow matching is a real and useful boundary lever, but it is not a one-scalar golden-seed fix. It shows that the upper liquid-traffic profile, not just the overhead drum, must be reconciled with the model topology and the active/no-active phase-transfer assumptions.
      - Francis holdup inversion / active liquid hydraulics probe:
        - tool update: `tools/update_initial_holdups_from_francis.py` now supports writing a separate output workbook, Clapeyron PR density calls, and targeted stage-flow overrides through `--target-liquid-flow-lbmolph` / `--target-stages`.
        - generated workbook: `logs/c3c4_initializer_profile_coeff_trial1_liqhyd_rectifying5701_20260602.xlsx`, with stages `2-11` targeted to `5701.145898904781 lbmol/h` and all internal stages Francis-inverted to their selected target liquid traffic.
        - full liquid-hydraulic ownership run: `logs/column_summary_20260602_091731.csv`, using `--enable-liquid-hydraulic-override --liquid-hydraulic-override-alpha 1.0`, failed badly (`score=229.5`, temperature rate `5.81 F/s`).
        - damped ownership run: `logs/column_summary_20260602_092009.csv`, using `--liquid-hydraulic-override-alpha 0.25`, was also worse than the profile-flow baseline (`score=7.71`, temperature rate `1.16 F/s`).
        - interpretation: algebraic Francis inversion is useful infrastructure, but simply flipping active `L_out` ownership from profile to Francis creates a larger hydraulic/energy shock in this case. The current best short probe remains the profile-flow reflux-match run (`score=1.43`). Any future liquid-hydraulic initializer needs staged/ramped ownership, residual guards, or a simultaneous liquid-flow/energy reconciliation rather than an immediate full override.
      - staged/ramped liquid-hydraulic ownership probe:
        - runner guard update: explicit `--enable-startup-hydraulic-sequence` is now allowed in `--runtime-mode hydraulic`; parity, calibration, and total-reflux still disable it because those modes are intentionally source/topology-specific.
        - Francis-inverted workbook with startup sequence: `logs/column_summary_20260602_093116.csv`, using `--startup-sequence-liquid-on-sec 10 --startup-sequence-liquid-ramp-sec 120`, improved dramatically versus immediate Francis ownership but still failed (`score=2.61` at `60 s`, best logged `2.35` at `55 s`, temperature rate `0.275 F/s`).
        - original coefficient-profile workbook with the same startup sequence: `logs/column_summary_20260602_093452.csv`, also failed but was slightly better (`score=2.21` at `60 s`, best logged `2.09` at `55 s`, temperature rate `0.270 F/s`).
        - interpretation: staged hydraulic ownership avoids the severe impulse shock, but it still does not beat the no-Francis reflux-matched profile-flow baseline (`logs/column_summary_20260602_090810.csv`, `score=1.43`). Also, the Francis-inverted holdup workbook is worse even before useful hydraulic ownership is established, so do not use algebraic holdup inversion as the default initializer for this C3/C4 case. Keep the profile-flow reflux-matched seed as the current best practical short-window baseline, and treat active Francis ownership as a later dynamic-hydraulic transition that needs either much stronger reconciliation or a separate validated operating point.
      - liquid-holdup / temperature reconciliation tool:
        - implementation: `tools/reconcile_column_liquid_energy_seed.py` performs a bounded TRF least-squares setup for selected stages, varying liquid holdup scale factors and tray temperature deltas. It rebuilds `Tray EL (BTU)` from `ML*hL(T,P,x)` so the primitive temperature and conserved liquid-energy state remain consistent.
        - residual scaling follows the current design: total liquid residual as `dML/dt / ML_seed`, liquid-energy residual as `dEL/dt / (ML_seed*Cp_liq)`, plus small regularization penalties on `ML` scale and `T` delta. The first objective intentionally targets total liquid/energy closure only; component composition remains fixed.
        - evaluate-only PR audit: `logs/c3c4_initializer_profile_coeff_trial1_liqenergy_eval_20260602.liquid_energy_summary.json`, using the packed top-vapor, matched condenser-duty, and reflux-matched setup with active Francis hydraulics. Result: stage 2 dominates the scaled objective (`max |dML/ML|=0.02577 1/s`, `max |dEL/(ML*Cp)|=1.50 F/s`).
        - evaluate-only table audit: `logs/c3c4_initializer_profile_coeff_trial1_liqenergy_eval_table_20260602.liquid_energy_summary.json`, same setup with table thermo. It preserved the same stage-2 mass pattern but gave a different energy scale (`3.17 F/s`), so table mode is only a development aid until locally regenerated/validated for this case.
        - execution note: full TRF solves with live Clapeyron PR are currently too slow because finite-difference Jacobians require many RHS evaluations; even a 3-stage pilot timed out before returning. A local tri-diagonal `jac_sparsity` pattern was added to the tool so mass/energy rows only finite-difference neighboring selected stages plus diagonal regularization rows. This is correct and should reduce dense Jacobian work, but the first 3-stage table-mode solve with sparsity still timed out, so dense Jacobian setup is not the only bottleneck. A flushed tracker log (`logs/c3c4_initializer_profile_coeff_trial1_liqenergy_tracker_smoke_20260602.progress.log`) confirmed the timing split: initial RHS residual and each optimizer objective evaluation take about `41 s`, while state packing is effectively zero. Next implementation work should reduce the per-evaluation RHS/thermo cost, for example by using cached/batched thermo packets, a case-local regenerated table, coarser finite-difference controls, or a coordinate-search/Gauss-Seidel style update that accepts one stage at a time.
        - profiler/cache update: `tools/profile_single_rhs.py` now reproduces the C3/C4 RHS timing in isolation. The pre-fix profile (`logs/rhs_profile_dump.txt`) showed that table-mode RHS calls were falling through to the PR/DWSIM backend and rebuilding DWSIM on each backend flash (`_init_dwsim` called `40` times over two RHS calls). The backend setters are now idempotent, so repeated identical component/package configuration no longer invalidates the global DWSIM objects. The after-fix profile (`logs/rhs_profile_dump_after_dwsim_cache.txt`) reduced the final `column_rhs_wall_sec` from `41.08 s` to `0.391 s` and built the DWSIM property package only once. With this bottleneck removed, rerun the 3-stage liquid-energy TRF smoke before abandoning the optimizer path.
        - post-cache optimizer smoke: `logs/c3c4_initializer_profile_coeff_trial1_liqenergy_tracker_smoke_after_cache_20260602.xlsx` completed in about `33 s` with `--max-nfev 5` for stages `2-4`. The capped table-mode solve reduced max scaled mass from `0.02468 1/s` to `0.00407 1/s` and max scaled energy from `3.169 F/s` to `0.312 F/s`. This is not an accepted initialization seed, but it proves the liquid-energy reconciler is now fast enough for scoped experiments again.
        - rectifying-section solve: `logs/c3c4_initializer_profile_coeff_trial1_liqenergy_rectifying2_11_after_cache_20260602.xlsx` converged for stages `2-11` in about `50 s`, improving the scaled t=0 objective to `0.00409 1/s` max mass and `0.189 F/s` max energy. However, stage 2 hit both imposed bounds (`ML_scale=1.30`, `T_delta=+10 F`), and dynamic launch tests did not pass. Active Francis plus composition relaxation ended at `score=16.35` (`logs/column_summary_20260602_133934.csv`); active Francis without equilibrium ended at `score=11.43` (`logs/column_summary_20260602_134025.csv`); profile-flow/no-active-Francis from the same workbook ended at `score=5.45` (`logs/column_summary_20260602_134102.csv`). Treat this as a successful computational probe but not as a better practical baseline than the reflux-matched profile-flow run.
        - boundary-augmented rectifying solve: `tools/reconcile_column_liquid_energy_seed.py` now optionally adds scalar top-boundary DOFs (`--enable-top-boundary-dofs`) for top-drum vapor scale, top-drum liquid scale, condenser-duty trim, and reflux trim, plus direct selected-stage temperature-rate residuals (`--include-temperature-rate-residual`) and wider stage-2-specific bounds. The table-mode stages `2-11` solve with packed top vapor and matched condenser duty converged in about `87 s`: `logs/c3c4_initializer_profile_coeff_trial1_liqenergy_topboundary2_11_20260602.xlsx` reduced max scaled mass from `0.02468` to `0.00378 1/s`, max scaled energy from `3.169` to `0.0231 F/s`, and max selected `dT/dt` from `2.783` to `0.0278 F/s`. The optimizer mainly selected a macro reflux trim (`5701.15 -> 5273.04 lbmol/h`) and left condenser duty/top-drum totals essentially unchanged. A no-equilibrium-aligned repeat (`logs/c3c4_initializer_profile_coeff_trial1_liqenergy_topboundary2_11_noeq_20260602.xlsx`) reached nearly the same t=0 residuals.
        - launch result: the boundary-augmented liquid/energy seeds are not accepted golden seeds. With hidden restart re-entry disabled, the no-equilibrium dynamic launch still failed (`logs/column_summary_20260602_135710.csv`), ending at `score=15.32`, `ss_max_rel_state_rate_per_s=0.0243`, and `ss_max_temp_rate_F_per_s=2.30`; the live residual remained dominated by explicit vapor/liquid state propagation outside the scoped objective. Conclusion: scalar boundary trims plus tray `ML/T/EL` reconciliation are good diagnostics, but an accepted full-topology seed must either include explicit `tray_V` component residuals and vapor inventory/composition DOFs in the objective, or intentionally initialize under an algebraic/profile-flow vapor topology and transition vapor dynamics later.
        - existing vapor homotopy probe: the current runner-side startup sequence already approximates an algebraic/profile-flow vapor handoff by holding `vapor_flow_model=profile` before switching to `energy` vapor and then ramping liquid hydraulics. Applying this existing sequence to the no-equilibrium boundary-augmented workbook (`logs/column_summary_20260602_140121.csv`, `--enable-startup-hydraulic-sequence --startup-sequence-energy-on-sec 20 --startup-sequence-liquid-on-sec 30 --startup-sequence-liquid-ramp-sec 60`) improved the launch substantially versus immediate full hydraulics: score `5.75` at `30 s` versus about `15.3`, and `ss_max_temp_rate_F_per_s` was down to `0.129` by `60 s`. It still failed and began drifting upward after about `35 s`, ending at `score=9.19`, with the residual moving to `top_L` n-Pentane by `60 s`. Conclusion: the correct prototype location is the runner-managed startup sequence, not a permanent core-RHS topology change; however, the existing sequence is too coarse because it switches vapor closure abruptly. The next implementation should add an explicit vapor-flow homotopy/blend and residual guard rather than only delaying `energy` vapor.
        - explicit three-phase startup homotopy: the runner/RHS now support an opt-in vapor-flow blend for dynamic vapor closures. `ColumnInputs.vapor_flow_homotopy_beta` blends active vapor traffic as `(1-beta) * V_profile + beta * V_dynamic`; the runner exposes `--enable-startup-vapor-homotopy`, `--startup-sequence-profile-hold-sec`, `--startup-sequence-vapor-on-sec`, `--startup-sequence-vapor-ramp-sec`, `--startup-sequence-vapor-rel-rate-gate-per-s`, and `--startup-sequence-vapor-backoff-sec`. The intended startup order is: Phase 1 `alpha=0,beta=0` profile liquid/profile vapor; Phase 2 `alpha -> 1,beta=0` liquid hydraulics transition while vapor remains profile; Phase 3 `alpha=1,beta -> 1` guarded vapor transition.
        - three-phase probe results:
          - baseline vapor-on at `35 s`: `logs/column_summary_20260602_142725.csv`, final `60 s` score `9.27`, worst `top_L` n-Pentane, `ss_max_rel_state_rate_per_s=0.0278`, `ss_max_temp_rate_F_per_s=0.130`.
          - delayed vapor-on at `75 s`: `logs/column_summary_20260602_142931.csv`, final `60 s` score `9.25`. Summary diagnostics showed `beta=0.0` and `vflow_homotopy_active=0`, so the late top-drum n-Pentane drift occurs even before vapor dynamics are activated.
          - liquid-ramp-open comparison with the mass-residual gate effectively disabled: `logs/column_summary_20260602_143041.csv`, `alpha` ramped from `0.13` at `5 s` to `1.0` at `35 s` while `beta=0.0`; final `60 s` score `9.26`, worst `top_L` n-Pentane, and temperature rate worsened to `0.342 F/s`.
        - interpretation: the new three-phase mechanism is wired and diagnostic telemetry is now available, but it does not by itself create an accepted seed for the current no-equilibrium boundary-augmented workbook. The failure appears before vapor homotopy activation and persists with vapor profile locked, so the current blocker is liquid-hydraulic/top-boundary material-energy compatibility, especially the reflux drum/top_L heavy-component balance, not the timing of the vapor-flow beta handoff. Keep the new homotopy as infrastructure for later transition tests, but the next model-consistent initializer should focus on top_L/reflux-drum material closure under active liquid hydraulics, or on adding top boundary liquid/vapor residuals to the formal initialization objective.
        - top_L closure split: the RHS now reports the reflux-drum liquid component balance as condenser liquid in, reflux out, distillate out, and net component rate. The active-liquid/profile-vapor diagnostic (`logs/column_summary_20260602_162504.csv`) ended with total top_L accumulation of `+676.6 lbmol/h` (`8336.6` condensed in, `5273.1` reflux out, `2386.9` distillate out), but the component split was much larger: n-propane `-2399.7 lbmol/h`, n-butane `+2899.7 lbmol/h`, and n-pentane `+176.6 lbmol/h`. Forcing the existing top-level controller to use molar-holdup PV mode with `--ignore-workbook-level-pv-mode` nearly closed the total inventory drift (`logs/column_summary_20260602_163322.csv`, total top_L net `-51.2 lbmol/h`, distillate increased to `3114.7 lbmol/h`) but did not reduce the relative score (`9.26`) because the component residuals remained large: n-propane `-3058.4 lbmol/h`, n-butane `+2830.6 lbmol/h`, and n-pentane `+176.6 lbmol/h`.
        - interpretation of the top_L split: top level/distillate control is a useful boundary DOF for total holdup, but it does not solve the initialization defect. The live condenser condensate is much richer in n-butane and n-pentane, and poorer in n-propane, than the seeded reflux-drum liquid inventory. Since both reflux and distillate draws use the current drum liquid composition, a steady total-condenser/reflux-drum initial condition requires top_L composition to be reconciled with the live condensed overhead stream, not just a different distillate total. The next DD-032 initializer should include top_L composition/state residuals or a guarded top_L-to-condensate composition initialization step before attempting vapor beta activation.
        - hybrid total-reflux washout probe: `--startup-total-reflux-washout-sec` now lets a hydraulic startup run temporarily evaluate the RHS as total reflux, using the existing closed-boundary logic to suppress feed/products and return condensate as reflux. A short `30 s` washout (`logs/column_summary_20260602_182218.csv`) did not help the final `60 s` release; it ended at score `10.95` and produced a release shock. The reason is the reflux-drum composition time constant: with about `1389 lbmol` in top_L and about `8337 lbmol/h` recycle, the simple stirred-drum washout timescale is roughly `600 s`, so a 30-60 s wash only moves the drum composition modestly.
        - longer washout and direct alignment probes: a `300 s` closed washout (`logs/column_summary_20260602_182341.csv`) improved the score during the sealed run, reaching `3.20` at `250 s` and ending at `5.61`, but it did not create a clean accepted state; the final score was dominated by `tray_V` n-pentane and `ss_max_temp_rate_F_per_s=0.842`. The condensate/drum composition mismatch remained a moving target (`x_cond - x_drum` at `300 s`: n-propane `-0.414`, n-butane `+0.354`, n-pentane `+0.060`). A direct diagnostic initializer, `--init-align-top-liquid-to-condensate`, was added to preserve top_L total holdup but repack its composition from the live t=0 condensate. It applied cleanly (`logs/run_metadata_20260602_182925.json`, `max_dx=0.0846`) but only slightly reduced the 60 s score (`9.23` vs `9.26`) because the live condensate composition immediately moved away as upper-tray states evolved.
        - updated conclusion: hybrid total reflux is physically meaningful and useful as a startup experiment, but not a short shortcut for this seed. Drum-only composition initialization is also insufficient. The accepted-seed path needs coupled top-boundary reconciliation including at least top_L composition, stage-1/stage-2 compositions/temperatures, and condenser/reflux duties or flows, with the top_L split diagnostics as objective terms.
      - strict total-condense/top-anchor topology note:
        - the strict total-condenser material split can enforce zero vapor slip by returning all incoming overhead vapor as condensed liquid before the reflux-drum vapor state participates. That is correct as a total-condenser idealization in some modes, but it can also mask the top-boundary pressure defect during initialization by decoupling column vapor traffic from the reflux-drum vapor inventory.
        - accepted initialization work should therefore require a coupled top-boundary audit: `V_condensed_in`, `V_to_top_drum`, raw `P_top_drum_psia`, pressure-gate scale, condenser duty used/calculated, and stage-1/stage-2 pressure relation must all be physically consistent, not merely quiet under a strict zero-slip shortcut.
  - practical thermo guidance: do not build another idealized thermo shortcut until the existing acceleration knobs have been exhausted. For recipe development, prefer `--fast-startup --disable-restart-reentry-settling`, startup seed caching, or table/table-pool thermo if a valid table exists. Use Clapeyron PR for final audit/high-fidelity checks and for short wiring probes where the wall time is acceptable.

## Pragmatic Path: Continuous-Operating Checkpoint Initialization (2026-06-03)

### Problem Summary

After systematic exploration of initialization tools and techniques through June 2, 2026, a consistent pattern emerged:

- **Sequential/local fixes fail**: Pressure-flow closure improves P/V but worsens component holdup closure. Boundary composition fitting closes the top locally but moves the residual to untargeted interior stages. Smooth profile correction avoids local moving-interface failures but is dimensionally too blunt to capture vector structure of the real problem.

- **The underlying deficiency is structural, not local**: The reflux-drum liquid composition cannot be initialized independently because it couples to:
  - Condenser duty (which depends on stage-2 vapor composition and temperature)
  - Condensate inflow composition (which depends on the live top vapor state)
  - Reflux/distillate outflow composition (which depends on the current drum state)
  - Stage-2 inlet composition feedback (which affects liquid profile, feed-stage balance, and pressure/vapor-flow profile)

- **This is a true DAE consistent initialization problem**: It cannot be solved by adjusting profiles or boundaries sequentially. It requires simultaneous closure of pressure, flow, composition, temperature, and energy across the entire column, exactly as Pantelides (1988) mathematically proved necessary.

### Best Observed Checkpoint: t=60s, score≈1.43

Using the synchronized pressure-flow seed plus top-anchor pressure control and matched condenser duty/reflux flow, the model reaches:

**At t=60s**: 
- `score=1.43`
- `max_rel_state_rate_per_s≈0.00463`
- `ss_max_temp_rate_F_per_s≈0.352` (below tolerance `0.15 F/s` is optimal, above is questionable)
- Dominant residual at stage-2 n-Butane (transitional)

**Key observation**: This is **not** a true steady state. The score continues to drift:
- t=60s: 1.63
- t=90s: 1.96
- t=120s: 8.21 (fails)

The checkpoint is a **local minimum in a drift trajectory**, not convergence.

### Assessment: When Is score≈1.43 "Close Enough"?

| Use Case | Recommendation |
|----------|---|
| **Validation disturbance studies** (<100s horizon) | ✓ Acceptable as quasi-settled operational baseline |
| **Short-duration controller tuning** | ✓ Acceptable as starting point |
| **Tier 1 source-topology comparison** | ✓ Acceptable if source-equivalent features are used |
| **Long-horizon studies** (>300s) | ✗ Will drift and eventually fail |
| **Claims of "steady-state initialization"** | ✗ Not sufficiently converged |
| **Archive as canonical golden seed** | ✗ Not stable under restart (reload spike to score 135) |

### Recommended Implementation: Binary Checkpoint Serialization

Rather than continuing to chase a static Excel-based golden seed (which is mathematically impossible for this DAE system), **use the t=60s quasi-settled checkpoint as a practical operational baseline**:

#### 1. Capture the Full State at t=60s

Instead of Excel workbook restart (which lost controller state, hydraulic memory, and thermo cache), implement native binary checkpoint serialization:

```python
checkpoint_dict = {
    'timestamp_seconds': 60.0,
    'state_vector_y': y_full[t=60s],        # full differential state
    'tray_L': tray_L[:, t=60s],
    'tray_V': tray_V[:, t=60s],
    'tray_T': tray_T[t=60s],
    'top_L': top_L[t=60s],
    'top_V': top_V[t=60s],
    'bottom_L': bottom_L[t=60s],
    'bottom_V': bottom_V[t=60s],
    'P_tray_hyd': P_tray_hyd[t=60s],
    'V_out': V_out[t=60s],                  # vapor flow profile
    'L_out': L_out[t=60s],                  # liquid flow profile
    'top_pressure_mv_cmd_btuph': top_pressure_mv_cmd[t=60s],
    'top_pressure_prev_error': top_pressure_error[t=60s],
    'condenser_duty_packet': condenser_duty_prev,
    'controller_memory': {
        'level_integrator_top': level_integ[top],
        'level_integrator_bottom': level_integ[bottom],
        'pressure_integrator': pressure_integ,
        'distillate_comp_integrator': xD_integ,
        'bottoms_comp_integrator': xB_integ,
    },
    'thermo_cache': {...},                  # reusable flash results
    'hydraulic_memory': {...}               # prior step profiles
}

# Save as pickle, HDF5, or msgpack (not Excel)
import pickle
with open('c3c4_checkpoint_t60s_quasi_settled.pkl', 'wb') as f:
    pickle.dump(checkpoint_dict, f)
```

#### 2. Implement Checkpoint Loader in Runner

Modify `dynamic_run_scaffold_v1.py` to support `--init-from-checkpoint` mode:

- If checkpoint is provided, skip startup conditioning (vapor re-init, thermo reconditioning, top-drum steadying)
- Load state vector and controller memory directly
- Resume from t=60.001s marching forward
- Disable all "fresh startup" logic

#### 3. Validate Restart Behavior

Test whether checkpoint restart preserves low-residual state:
- From checkpoint: continue to t=120s
- If score stays <2.0 through t=120s, checkpoint is usable
- If score immediately spikes (like the Excel restart did), checkpoint needs richer state capture

#### 4. Document as Operational Baseline, Not Golden Seed

Update documentation to clarify:

```
CHECKPOINT USAGE MODEL:
- This is a "quasi-settled continuous operating point," not a "true steady-state initialization."
- Use for: disturbance validation, control tuning, short-horizon studies (<100s)
- Do NOT use for: steady-state claims, long-horizon dynamics (>300s), thermal creeping
- Score at checkpoint: 1.43 (not at equilibrium)
- Expected behavior: score remains <2.5 for ~100s, then drifts upward
```

### Path Forward

#### Short Term (1-2 weeks)
1. Implement binary checkpoint capture and loader
2. Test restart behavior at t=60s
3. Use checkpoint for Tier 1 validation disturbance studies
4. Document limitations clearly

#### Medium Term (3-4 weeks)
1. Build `tools/solve_reflux_drum_composition.py` as a test of whether reflux-drum closure alone helps
2. If it improves t=120s behavior (e.g., score <5), pursue full coupled boundary initialization
3. If not, confirms the problem is systemic and Pantelides approach is necessary

#### Long Term (6-8 weeks)
1. Implement full whole-column consistent initialization solver (Pantelides-style)
2. Or accept that this model's natural state is continuous operation under control, not static Excel snapshots

### Why This Is the Right Call

- **Mathematically honest**: Acknowledges the DAE under-constraint instead of pretending a new heuristic will fix it
- **Practically useful**: Enables validation work and controller development to proceed
- **Staged learning**: t=60s checkpoint experiment will teach us whether the deficiency is shallow (reflux-drum local) or deep (systemic)
- **Deferred commitment**: Doesn't lock us into a full Pantelides solver until we're sure it's necessary

Related issues:
- `DD-030`: Gani/ChemSep model-topology reconciliation.
- `DD-031`: profile-flow parity conflict with explicit tray vapor states.
- `DD-032`: dynamic initialization cannot rely on raw ChemSep profiles as full model-consistent initial conditions.
