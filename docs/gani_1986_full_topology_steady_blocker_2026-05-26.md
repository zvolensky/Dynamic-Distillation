# Gani 1986 Full-Topology Steady-State Blocker

Date: 2026-05-26

This note records the current state of the Gani/Ruiz/Cameron debutanizer case after testing whether the full model-topology workbook can simply be marched to steady state.

## Run Tested

Continuation run:

```powershell
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel "logs\gani_debutanizer_chemsep_seed_diam597_parity_qcond_prvap_noeq_noVrelax_60s\validation_gani_1986_debutanizer__restart_20260525_214949.xlsx" `
  --thermo clapeyron `
  --clapeyron-model PR `
  --runtime-mode parity `
  --include-energy `
  --no-equilibrium `
  --vapor-holdup-relaxation-sec 0 `
  --condenser-duty-mode specified `
  --condenser-duty-btuph -12269989.464019539 `
  --n-steps 1200 `
  --dt 0.2 `
  --log-every 100 `
  --allow-repeat-command `
  --logs-dir logs\gani_full_topology_pr_continue_300s_noeq_noVrelax
```

Key output files:

- `logs/gani_full_topology_pr_continue_300s_noeq_noVrelax/column_summary_20260526_082510.csv`
- `logs/gani_full_topology_pr_continue_300s_noeq_noVrelax/column_profile_20260526_082510.csv`
- `logs/gani_full_topology_pr_continue_300s_noeq_noVrelax/validation_gani_1986_debutanizer__restart_20260526_082510.xlsx`

The run continued a previous 60 s restart by another 240 s of visible simulation time. It did not converge:

- `steady_state_flag = 0`
- final `steady_state_score = 74.6555`
- final `ss_max_rel_state_rate_per_s = 0.223966`
- dominant state: `tray_V`, stage `13`, component `Isobutene`
- final `ss_max_temp_rate_F_per_s = 0`

The score was not monotonically decaying toward zero. It was about `77.52` at 120 s and `74.66` at 240 s, so the case appears stuck on a structural mismatch rather than slowly approaching steady state.

## Follow-Up Reconciliation Audit

The final restart workbook was audited directly:

```powershell
python tools\gani_stage_reconciliation_audit.py `
  --excel "logs\gani_full_topology_pr_continue_300s_noeq_noVrelax\validation_gani_1986_debutanizer__restart_20260526_082510.xlsx" `
  --thermo clapeyron `
  --clapeyron-model PR `
  --runtime-mode parity `
  --include-energy `
  --no-equilibrium `
  --vapor-holdup-relaxation-sec 0 `
  --condenser-duty-mode specified `
  --condenser-duty-btuph -12269989.464019539 `
  --use-excel-vapor-holdup `
  --startup-thermo-conditioning-iters 0 `
  --output-dir logs\gani_full_topology_pr_steady_blocker_audit_20260526
```

Audit outputs:

- `logs/gani_full_topology_pr_steady_blocker_audit_20260526/summary.md`
- `logs/gani_full_topology_pr_steady_blocker_audit_20260526/stage_reconciliation.csv`
- `logs/gani_full_topology_pr_steady_blocker_audit_20260526/component_reconciliation.csv`

Headline audit result:

- stage 28 total material residual: `+1231.76 lbmol/h`
- bottom pool material residual: `-1231.76 lbmol/h`
- worst component residual: stage 12 `Isobutene`, `-824.092 lbmol/h`
- worst energy residual: stage 12, `-816547 Btu/s`

This confirms the same bottom-boundary topology conflict seen earlier: the explicit full model has a bottom sump/reboiler boundary state, while the ChemSep profile already includes terminal reboiler/product behavior. The full-topology workbook is therefore not a model-equivalent steady seed.

## Interpretation

The Gani candidate currently has two valid but different uses:

1. Source-topology material parity, using the ChemSep `x/y/L/V` profile together and disabling extra boundary/vapor states. This passes and is a useful real-component material-balance regression.
2. Full model-topology dynamic validation, using explicit condenser drum, bottom sump, tray vapor states, and energy. This does not yet pass and should not be advanced by simply running longer.

The next useful development task is a model-topology steady initialization/reconciliation step. The first target should be bottom sump/reboiler coupling, because the dominant total residual is exactly the boilup-sized transfer between stage 28 and the bottom pool.

## First Explicit-Sump Conversion

An explicit-sump seed workbook was created:

- Tool: `tools/create_gani_model_topology_seed.py`
- Workbook: `validation_gani_1986_debutanizer_model_topology_seed.xlsx`

The conversion changes only the terminal liquid-flow interpretation:

- stage 28 `Liquid Flow (lbmol/h)`: `586.826458` -> `1818.58773`

Rationale: the ChemSep/source value is the bottoms product rate from the terminal reboiler. In the full model topology, stage 28 drains to an explicit bottom sump/reboiler, so its liquid outflow must be approximately bottoms plus boilup.

Audit result after this conversion:

- audit folder: `logs/gani_model_topology_seed_audit_20260526`
- max total stage material residual fell to `0.000793664 lbmol/h`
- bottom pool material residual fell to `8.81761e-05 lbmol/h`
- remaining max component residual: `186.403 lbmol/h`, stage 28 `Benzene`
- remaining largest energy residuals: stage 1 `-3438.43 Btu/s`, stage 28 `2960.24 Btu/s`

This confirms the explicit-sump liquid-flow conversion fixes the gross total material topology mismatch. It does not make the case a full PR steady state because the liquid/composition profile remains ChemSep-source-derived while the vapor profile is Clapeyron-PR-derived.

A 60 s dynamic run of this converted workbook still failed to settle:

- run folder: `logs/gani_model_topology_seed_pr_60s_noeq_noVrelax`
- final `steady_state_flag = 0`
- final `steady_state_score = 65.7537`
- final `ss_max_rel_state_rate_per_s = 0.197261`
- dominant state: `tray_V`, stage 24, component `1-pentene`

Current conclusion after the first conversion: the full-topology seed now has the right bottom total-flow accounting, but still needs a PR-consistent composition/energy reconciliation. This should be treated as a steady-state initialization solve, not a longer dynamic march.

## Material-Only Reconciliation

A material-only full-topology reconciliation pass was added:

- Tool: `tools/reconcile_gani_model_topology_material_seed.py`
- Workbook: `validation_gani_1986_debutanizer_model_topology_material_reconciled.xlsx`

This tool keeps the corrected explicit-sump liquid flow profile and the current PR vapor profile, then recomputes tray liquid compositions so component balances close under the explicit top/bottom model topology. It also aligns the condenser-transfer liquid and top/bottom boundary liquid compositions with the reconciled terminal transfer states.

The tool completed without negative-component clipping:

- `max_abs_liquid_composition_delta = 0.10249881`
- `min_raw_component_before_clip = 0`
- internal material-balance residual from the tool: `0.000424513 lbmol/h`

Audit result:

- audit folder: `logs/gani_model_topology_material_reconciled_audit3_20260526`
- max total stage material residual: `0.000793664 lbmol/h`
- max component material residual: `0.000424513 lbmol/h`
- top pool material rate: `0.00044096 lbmol/h`
- bottom pool material rate: `8.81761e-05 lbmol/h`

This satisfies the intended step-3 objective: the full-topology Gani seed can now be made material-balanced under fixed PR vapor/profile-flow assumptions.

A short dynamic verification attempt using this workbook did not pass steady:

- run folder: `logs/gani_model_topology_material_reconciled_noenergy_60s`
- final `steady_state_score = 65.7537`
- final `ss_max_rel_state_rate_per_s = 0.197261`

However, this run is not a clean rejection of the material reconciliation. Startup/re-entry conditioning still perturbed the reconciled state before marching (`max_dy = 0.246` reported during startup conditioning). The next model-initialization task is therefore to add or identify a true "preserve reconciled seed" startup path before using dynamic marching as verification.

## Preserve-Startup and Vapor-State Follow-Up

The runner now exposes `--disable-restart-reentry-settling`, which skips hidden re-entry conditioning for explicit restart/boundary-state workbooks. This preserves deliberately reconciled workbooks through startup.

After adding the flag, the material-reconciled workbook was rerun with:

```powershell
--disable-startup-thermo-conditioning
--disable-restart-reentry-settling
--use-excel-vapor-holdup
--no-equilibrium
```

The hidden startup perturbation was removed, but the dynamic run still failed with a `tray_V` residual. This showed the next distinction:

- the first material reconciliation closed total component balances,
- but dynamic full-topology runs also require separate tray liquid and tray vapor holdup balances.

The reconciler was therefore extended with `--reconcile-vapor-profile`, which recomputes vapor compositions from the fixed vapor-traffic profile before recomputing liquid compositions.

Vapor-convective reconciliation result:

- workbook: `validation_gani_1986_debutanizer_model_topology_material_reconciled.xlsx`
- audit folder: `logs/gani_model_topology_material_reconciled_vaporconv_audit_20260526`
- max component material residual: `0.000196092 lbmol/h`
- max total stage material residual: `0.000793664 lbmol/h`
- max vapor-composition movement from the PR-seeded profile: `0.47981389`

The large vapor-composition movement is important: this is a model-topology material-balance construction, not a PR-equilibrium validation state.

Dynamic reruns with preserved startup still did not pass:

- `logs/gani_material_reconciled_vaporconv_preserve_60s`
- `logs/gani_material_reconciled_vaporconv_nofeedflash_60s`
- final score remained about `62.5`, driven by `tray_V`

The remaining mechanism is the feed tray phase-traffic discontinuity. Around stage 23, the fixed `L/V` profile requires substantial liquid-to-vapor phase redistribution at the feed tray. The total component balance closes, but separate phase holdups move unless an energy/equilibrium/flash mechanism supplies the phase conversion consistently.

Current conclusion: step 3 succeeded for total material topology and clarified the next blocker. A full vapor-state dynamic steady seed cannot be obtained by pure component bookkeeping alone; it needs a feed-stage phase/energy reconciliation or a source-topology/algebraic-vapor formulation.
