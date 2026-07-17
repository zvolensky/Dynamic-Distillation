# Dynamic Model Current State

> Historical snapshot dated 2026-07-08. For the authoritative current position, see `docs/dynamic_model_current_state_2026-07-12.md`.

Date: 2026-07-08

This note records the current working interpretation of the C3/C4 dynamic-column work after the initializer, residual-solver, checkpoint, and controller probes run during July 6-8, 2026.

## Executive Summary

The model is healthier than it was at the start of this work, but it should not yet be called fully validated or production-ready.

The best current recipe can complete a bounded short dynamic run and can pass the current 900 s rate-based dynamic gate under the linear-steady/equilibrium-guard configuration. That is real progress, but the acceptance gate was incomplete. A K-state drift audit shows that `K_state` does not converge to `K_thermo` during the 900 s run: the final max absolute K error is about `1.65`, the final max absolute `ln(K_state/K_thermo)` is about `1.93`, and the absolute K error regrows about `0.745` from the run minimum. An 1800 s extension then showed that the 900 s pulse envelope was not safely damped: the score rebuilt after about 920 s, reached about 6.09 at 1200 s, then jumped above 500 by 1240 s. The model is therefore not healthy over the longer horizon.

The main blocker is no longer simply "find a better Excel seed." The remaining issue is dynamic-model consistency: pressure, vapor flow, vapor composition, energy closure, equilibrium relaxation, and boundary ownership must remain mutually consistent during integration.

## Current Working Baseline

The current best baseline is the C3/C4 initializer residual vapor-state stage-2 seed launched with the linear-steady/equilibrium-guard runtime recipe, including the native checkpoint path:

- primary run family: `logs/c3c4_stage2_liq_eq_vap_linearsteady_900s_eqcompguard_m1_20260708/`
- representative checkpoint: `c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_20260708_084013.npz`
- no-energy checkpoint diagnostic: `c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_no_energy_20260708.npz`

This baseline is the current reference for comparisons. It is not a certified zero-residual initialized state.

K-consistency follow-up:

- report: `logs/k_state_drift_gate_900s_eqcompguard_m1_20260708.md`
- status: failed the new K-level gate
- final max `|K_state - K_thermo|`: about `1.647`
- final max `|ln(K_state/K_thermo)|`: about `1.932`
- positive trend from the run minimum: about `0.745`
- dominant final row: generic interior stage 5, n-pentane
- interpretation: the existing 900 s dynamic gate can pass a rate-based run while a physical equilibrium-consistency level metric is worsening underneath it.

Equilibrium-transfer guard follow-up:

- mechanism: `_limit_equilibrium_component_transfer_by_transport()` caps equilibrium component-transfer against the local pre-equilibrium vapor material RHS.
- interpretation: the cap is load-bearing. At multiplier `1.0`, the guard suppresses same-direction amplification and gives the better 300 s rate score, but it also leaves K-state drift unresolved.
- existing 300 s comparison:
  - multiplier `1.0`: final score `2.26`, peak score `22.68`, final max `|K_state-K_thermo| = 1.39`, positive K-delta trend `0.50`
  - default/sign-aware multiplier `1.5`: final score `3.00`, peak score `50.03`, final max `|K_state-K_thermo| = 0.875`, positive K-delta trend `0.0`
- conclusion: loosening the cap improves K consistency, confirming the guard is a likely cause of K drift, but worsens the vapor-material wave. Neither setting satisfies the combined rate plus K-level acceptance criteria.

Longer-run follow-up:

- run family: `logs/c3c4_stage2_liq_eq_vap_linearsteady_1800s_eqcompguard_m1_20260708/`
- final status: failed at 1800 s with score about `540`, relative state rate about `1.62 1/s`, and max temperature rate about `21.1 F/s`
- key transition: score rose from about `6.09` at 1200 s to about `538` at 1240 s
- focused vapor RHS audit at 1240 s: stage 12/13 vapor transport dominates, especially n-propane and n-butane
- focused energy audit at 1240 s: vapor-flow calc/used mismatch remains zero, but stage 12/13 energy residual and temperature-rate terms activate

Fine-trace follow-up on 2026-07-09:

- run family: `logs/c3c4_stage2_liq_eq_vap_linearsteady_1300s_eqcompguard_m1_fine_20260709/`
- result: the transition is sharper than the sparse 1800 s logs showed. The score rises smoothly to about `6.09` at `1200 s`, then jumps to about `438.7` by `1205 s`.
- focused vapor/energy audits at `1200 s` and `1205 s` show that vapor-flow calc/used closure remains internally matched, while the temperature/energy residual activates and the material residual concentrates at the same generic interior region.
- new liquid-inventory audit: `logs/liquid_inventory_depletion_eqcompguard_m1_fine_20260709.md`
- key finding: one internal tray liquid inventory drains from normal startup inventory to `0.208 lbmol` at `1200 s`; shortly afterward the liquid composition makes a `0.972` mole-fraction step. The equilibrium-transfer term is still zero at the failure point.
- interpretation: the long-horizon failure now appears to be preceded by slow internal liquid-inventory depletion under profile liquid traffic, followed by an explicit composition snap when the inventory becomes too small. This is a generic small-inventory/timestep-sensitivity problem, not evidence for a tray-specific code path.

## What Improved

Several defects or misleading paths have been clarified:

- Raw ChemSep/Excel steady-state profiles are now treated as seeds, not accepted dynamic initial states.
- Native checkpoint reload is preferred over Excel-only restart for accepted artifacts because it preserves packed dynamic state and selected runtime memory.
- The dynamic smoke gate now gives a cleaner acceptance question: whether a candidate is dynamically usable, not merely whether a static residual norm improved.
- Provider enthalpy precedence and top-boundary reflux enthalpy ownership were tightened.
- The positive feed-stage-flash CLI flag now propagates into `RunnerConfig`, and the runtime profile logs the effective feed-flash flag and feed liquid/vapor split.
- The no-lag/zero-temperature-target diagnostics separated initialization memory effects from physical RHS behavior.
- The 900 s linear-steady/equilibrium-guard recipe demonstrated that the model can be made bounded under a disciplined runtime configuration.

## What Did Not Work

The following should remain diagnostic only, not acceptance paths:

- broad least-squares residual tuning as a standalone initializer,
- direct projection of stored tray energy states,
- stripping energy states and declaring the remaining checkpoint accepted without further vapor/material closure,
- one-shot Francis liquid-holdup projection,
- targeted liquid-holdup least-squares solve,
- local profile nudging that improves one residual family while worsening dynamic behavior.

The recent liquid-holdup projection/solve branch should be considered closed for now. It did not reduce the dominant residual and worsened or left unchanged the relevant material residuals.

## Current Failure Modes

The remaining symptoms are:

- nonzero vapor/material motion after restart,
- pressure drift during longer reload probes,
- explicit vapor-state residuals that can become concentrated around the feed-adjacent generic interior interface during longer runs,
- slow internal liquid inventory depletion under fixed/profile liquid traffic, followed by a near-empty-inventory composition snap,
- the earlier feed-stage TP flashing failure was traced to an indeterminate single-phase `K ~= 1` feed flash being interpreted as a 50% vapor split; after the fallback fix, the same 300 s feed-flash run preserves the all-liquid bubble-point feed and no longer drains the feed-region inventory,
- K-state/K-thermo level inconsistency that regrows even while the rate-based 900 s gate passes,
- sensitivity to whether energy states are present as independent state blocks,
- controller interactions that can amplify but do not fully explain the startup motion.

These should be treated as coupled dynamic-model issues rather than as a simple controller-tuning problem or a simple initializer-variable-selection problem.

## Controller Interpretation

Level controllers can improve operational behavior when they use geometry-based level measurements and reasonable tuning. More aggressive top-drum controller settings may help hold inventory, but controller tuning should not be used to hide initialization or model-coupling defects.

A clean initialization should not produce large early waves. Some settling is normal in a rigorous explicit vapor/energy model, but large oscillations or pressure/composition surges indicate unresolved consistency errors.

## Implicit Dynamic Model Question

A broader implicit simultaneous solve across pressure, vapor flow, energy, and phase terms is a plausible long-term dynamic-model architecture. It could reduce splitting error and make the runtime model behave more like a proper DAE system.

It should not be the immediate next engineering commitment. The recent defect history matters: several apparent "deep architecture" problems were specific consistency defects in the existing explicit/sequential implementation, including pressure-anchor ordering, reflux enthalpy ownership, feed/flash option propagation, and thermo/enthalpy source precedence. That pattern argues for one more focused root-cause pass before investing in a broader implicit block.

If an implicit solve is introduced later, it should not arrive as one giant rewrite. The recommended path is incremental:

1. use the current explicit model and audits to identify which algebraic closures are fighting,
2. promote one closure family at a time into a simultaneous residual solve,
3. compare each change against the current 900 s baseline,
4. keep the dynamic gate and residual audits as acceptance criteria.

## Recommended Next Play

1. Keep the current 900 s linear-steady/equilibrium-guard case as the short-horizon reference baseline, but do not treat it as accepted health because it fails K-level consistency.
2. Do not continue the liquid-holdup projection/solve branch unless new evidence changes the residual ranking.
3. Add K-state drift to initializer acceptance: a run must satisfy rate, endpoint, and K-level consistency gates.
4. Treat the equilibrium-transfer guard as the active tradeoff to resolve: `1.0` is dynamically calmer but off-equilibrium, while `1.5` is more K-consistent but dynamically worse.
5. Trace the K-state divergence path first, especially n-pentane around the generic interior stages 5-7, then relate that to the later 1200-1240 s feed-adjacent failure.
6. Treat the 1800 s failure as the active long-horizon root-cause target: focus on the transition from 1200 s to 1240 s.
7. Add the liquid-inventory depletion audit to the long-horizon acceptance evidence. A dynamically acceptable run must not let an internal tray drift near empty liquid inventory before the apparent vapor/energy failure.
8. Do not use `--flash-feed-at-stage-conditions` as the next initializer acceptance recipe. With the CLI handoff fixed it worsens the current case, even though it is the more rigorous feed-treatment direction in principle.
9. Run a focused vapor-material/energy root-cause pass around the generic interior interface that lights up after the low-inventory event.
10. Treat the no-energy checkpoint reload as a degraded/partial-state restart stress test, not by itself as proof that the core full-state dynamic architecture is unsound.
11. Build or refine a coupling audit that compares the runtime ownership of pressure, vapor flow, enthalpy, equilibrium target, boundary streams, and liquid inventory at the same time snapshots.
12. Only change equations where that audit identifies a concrete owner mismatch, split-form inconsistency, or timestep-unsafe state update.
13. Keep accepted initializer artifacts checkpoint-native until Excel reload parity is proven.

## Bottom Line

Stay the course, but narrow the course.

The project is no longer on the earlier fruitless path of trying to force a raw steady-state profile into a rigorous dynamic model. The productive direction is now model-coupling diagnosis and incremental DAE-like closure, with the initializer serving as a gate and artifact generator rather than the sole place to fix runtime inconsistency.
