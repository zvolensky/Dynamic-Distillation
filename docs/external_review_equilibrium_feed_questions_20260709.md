# External Review Collection: Equilibrium, Feed Flashing, and Stage-12 Failure

Date: 2026-07-09

## Purpose

This note collects the current questions and findings around the latest C3/C4 dynamic initialization/runtime investigation. It is intended for external review.

## Questions for Review

### 1. Should equilibrium be turned off for these runs?

Short answer: no, not for the full rigorous C3/C4 dynamic model.

The CLI switch `--no-equilibrium` disables equilibrium relaxation. It is useful for reduced source-topology validation cases and isolation diagnostics, especially when the source model has algebraic vapor composition and no explicit vapor holdup ODE. It is not a realistic final recipe for the full hydrocarbon dynamic model with explicit vapor states, pressure, energy, and PR-style thermodynamics.

The latest fine run did not use `--no-equilibrium`. It used:

```text
--equilibrium-relaxation-mode composition-only
--equilibrium-tau-sec 0.5
--equilibrium-component-transfer-max-cancel-multiplier 1.0
```

So equilibrium relaxation was active, but constrained by the component-transfer guard. The focused vapor RHS audits show that `equilibrium_transfer` was effectively zero at the failure point. That is different from intentionally disabling equilibrium; it means the active relaxation mechanism was not correcting the state where the failure emerged.

Recommendation: keep `--no-equilibrium` in the codebase as a diagnostic/source-validation switch, but remove it from full C3/C4 rigorous runtime and initializer-acceptance runs.

### 2. Why is the feed not flashed at stage conditions?

The switch `--no-flash-feed-at-stage-conditions` tells the runtime to preserve the workbook/source feed split rather than recompute the feed vapor/liquid split at the live feed-stage pressure/temperature.

Why it was used: earlier feed flashing introduced startup discontinuities because the imported seed, runtime thermo, pressure basis, and enthalpy basis were not fully aligned. Preserving the workbook feed split was a diagnostic way to avoid moving the feed packet while other coupling defects were being isolated.

Is this realistic? Only partly. It is defensible for source-preservation diagnostics, but a final rigorous dynamic model should handle the feed from a consistent specification: flow, composition, temperature or enthalpy, pressure, and phase state. The model should then reconcile that feed through the stage material and energy equations.

Could it be responsible for the stage-12 failure? It could contribute, because the failure occurs at the feed-region internal tray. However, the current evidence points to a more specific immediate mechanism: liquid inventory depletion followed by a timestep-sensitive composition snap.

Recommendation: run a controlled A/B test with the same recipe but without `--no-flash-feed-at-stage-conditions`. Compare the liquid-depletion audit, feed split, stage liquid inventory, and the score around `1200-1205 s`.

### 2026-07-09 correction after the controlled A/B

The first attempted A/B was invalid. Removing `--no-flash-feed-at-stage-conditions`
did not activate feed flashing in hydraulic mode, and the positive
`--flash-feed-at-stage-conditions` CLI flag was not being copied into
`RunnerConfig`. The profile and summary CSVs were therefore identical except for
wall-clock fields.

That CLI handoff is now fixed, and the runtime profile now logs:

- `feed_flash_at_stage_conditions`
- `feed_liquid_rate_lbmolps`
- `feed_vapor_rate_lbmolps`
- `feed_effective_vapor_fraction`

With the fixed positive flag, the feed-flash case is not better for this
recipe. A 300 s run:

```text
logs/c3c4_stage2_stagefeedflash_fixed_300s_20260709/
```

shows the feed-stage split toggling between all-liquid and 50% vapor. When the
split moves to 50% vapor, the feed-stage liquid source drops and the internal
liquid inventory drains rapidly:

- at `150 s`: score about `7.71`
- at `155 s`: score about `39.9`; feed effective vapor fraction `0.5`
- at `200 s`: score about `490.7`; liquid inventory about `0.156 lbmol`
- at `300 s`: score about `445.6`

The corresponding audit:

```text
logs/liquid_inventory_depletion_stagefeedflash_fixed_300s_20260709.md
```

fails with one risky internal stage, minimum liquid inventory `0.1555 lbmol`,
worst update fraction `5.17`, and a full `1.0` composition step.

The feed-stage equation audit:

```text
logs/feed_stage_equation_audit_stagefeedflash_fixed_300s_20260709.md
```

adds an important distinction. The feed-stage material accounting itself closes:
liquid total closure residual is `0`, feed-liquid residual is `0`, and the
pre-phase liquid flow residual is numerical noise. The pressure basis delta is
also `0`. The failure is therefore not a simple feed-stage mass-balance coding
mistake. It is a dynamically harsh but internally consistent split change: the
effective feed vapor fraction steps by `0.5` at `155 s`, the liquid feed source
drops, liquid inventory collapses, and then composition/energy terms become
timestep-sensitive.

Current conclusion: feed flashing is not the cure for the long-horizon failure
under the current recipe. Preserving the workbook/source feed split is less
realistic, but it is currently more dynamically benign. A final rigorous model
still needs a consistent feed treatment, but the immediate problem is that the
stage-feed flash creates a discontinuous effective feed split that the current
explicit liquid-inventory/composition update cannot tolerate.

### 2026-07-09 correction to the feed-flash split interpretation

The 50% feed vapor split above was later traced to a numerical/logic artifact,
not a physical flash result. The feed stream was specified at approximately its
bubble point with workbook vapor fraction `0.0`. For the C3/C4 feed, the
Clapeyron PR provider returned an unresolved/single-phase packet with
`K = [1, 1, 1]`. In that case the Rachford-Rice residual is identically zero,
so vapor fraction is indeterminate. The previous code allowed the bisection
midpoint to become the effective split, producing an artificial `beta = 0.5`.

The feed split logic now treats that `K ~= 1` packet as indeterminate and falls
back to the source stream vapor fraction instead of inventing a 50/50 split.
For this feed, the corrected stage-flash path gives:

```text
feed effective vapor fraction = 0.0
feed liquid rate = 1.98416036 lbmol/s
feed vapor rate = 0.0 lbmol/s
```

A same-command 300 s rerun with feed-stage flashing enabled:

```text
logs/c3c4_stage2_stagefeedflash_k1fix_300s_20260709/
```

no longer drains the feed-stage liquid inventory. The updated audit:

```text
logs/feed_stage_equation_audit_stagefeedflash_k1fix_300s_20260709.md
```

reports minimum feed-stage liquid inventory `38.3486 lbmol`, max feed
vapor-fraction step `0`, peak score `23.0505`, and final score `2.281`.
Therefore, the previous 300 s feed-flash failure should be interpreted as a
feed split edge-case bug, not evidence that realistic feed flashing itself is
destabilizing.

## Current Evidence

### Fine trace confirms a sharp transition

Run:

```text
logs/c3c4_stage2_liq_eq_vap_linearsteady_1300s_eqcompguard_m1_fine_20260709/
```

The sparse 1800 s logs showed failure between `1200 s` and `1240 s`. The fine trace narrows this:

- at `1200 s`: score about `6.09`
- at `1205 s`: score about `438.7`
- at `1210 s`: score about `536.8`

This looks like a threshold event in the logged outputs, not a smooth slow exponential growth.

### Liquid inventory depletion is the best current precursor

New audit:

```text
tools/audit_liquid_inventory_depletion.py
logs/liquid_inventory_depletion_eqcompguard_m1_fine_20260709.md
```

Key finding:

- one internal tray liquid inventory falls to `0.208 lbmol` at `1200 s`
- the largest liquid composition step is `0.972` mole fraction shortly afterward
- terminal top/bottom equipment is excluded from the default internal-stage audit

Interpretation: the model is allowing an internal liquid inventory to drift nearly empty while large liquid traffic assumptions remain active. Once the inventory is tiny, the explicit composition update becomes fragile and snaps.

### Stage material and energy symptoms after the snap

Focused vapor RHS audits:

```text
logs/vapor_rhs_material_terms_eqcompguard_m1_fine_t1200_20260709.md
logs/vapor_rhs_material_terms_eqcompguard_m1_fine_t1205_20260709.md
```

At `1200 s`, the largest relative vapor RHS is modest. At `1205 s`, the dominant vapor material residual concentrates in the same internal feed-region area. The equilibrium-transfer term remains zero in the focused rows.

Focused energy audits:

```text
logs/energy_vapor_closure_eqcompguard_m1_fine_t1200_20260709.md
logs/energy_vapor_closure_eqcompguard_m1_fine_t1205_20260709.md
```

At `1200 s`, vapor-flow calc/used closure is clean and raw temperature rate is effectively zero. At `1205 s`, the energy/temperature residual activates. The vapor-flow calc/used mismatch remains zero, so the immediate problem is not a simple `V_calc - V_used` lag.

## Current Interpretation

The active failure is probably not caused by a single hardcoded tray behavior. The model appears to have a generic internal-stage weakness:

1. A small liquid material imbalance persists under the current liquid traffic assumptions.
2. The imbalance slowly drains an internal liquid inventory.
3. Once liquid inventory is very small, explicit composition updates become timestep-sensitive.
4. A large composition step then excites vapor transport, energy residuals, and K-state mismatch.

This is consistent with the user's genericity requirement: any code fix should be topology/generic and should not mention specific trays except true top and bottom boundary handling.

## Recommended Next Test

Run the same fine recipe with only one material change:

```text
remove --no-flash-feed-at-stage-conditions
```

Then compare:

- `tools/audit_liquid_inventory_depletion.py`
- stage liquid inventory minimum and timing
- feed liquid/vapor split
- stage material residual near the feed-region internal tray
- vapor RHS audit at the first bad time
- energy/vapor closure audit at the first bad time
- score trajectory around `1200-1205 s`

This test has now been run with the CLI handoff fixed. Feed flashing does not
prevent internal liquid inventory depletion; it accelerates a low-inventory
failure in the current recipe. The core issue remains liquid traffic/holdup
consistency and timestep-safe composition updating, with feed treatment as a
coupled stressor rather than the direct solution.

## Relevant Artifacts in Bundle

- this note
- `docs/dynamic_model_current_state_2026-07-08.md`
- `docs/initializer_requirements_and_acceptance.md`
- `docs/initialization_code_status.md`
- fine-run `column_summary`, `column_profile`, `run_metadata`, and startup trace
- focused vapor RHS audits at `1200 s` and `1205 s`
- focused energy/vapor closure audits at `1200 s` and `1205 s`
- liquid inventory depletion audit
- the native checkpoint and restart workbook written by the fine run
