# DD-011 Follow-up: Runtime Simplification And Hydraulics Findings

Date: 2026-02-21 (local)
Related root-cause report: `docs/dd_011_hydraulic_parity_drift_report_2026-02-19.md`

## Purpose

Document findings collected after the 2026-02-19 DD-011 root-cause write-up and record the implemented simplification path for ongoing diagnostics.

## New Findings

1. The runner now has explicit runtime behavior modes:
   - `parity`: force `Pressure=spec`, `VaporFlow=profile`, liquid-hydraulic override off.
   - `hydraulic`: force `Pressure=hydraulic`, `VaporFlow=energy`, liquid-hydraulic override on.
   - `legacy`: preserve prior spec/CLI-driven behavior.
2. Startup hydraulic sequencing is now intentionally bypassed in both simplified modes (`parity`, `hydraulic`) and remains applicable only in `legacy`.
3. The simplified modes make parity diagnostics deterministic by removing hidden startup-mode transitions.
4. Hydraulic+energy startup remains numerically stiff in short checks; the runner emits an explicit warning under `hydraulic` mode with `condenser-duty-mode=total-condense`.

## Evidence Snapshot

Code paths implementing the simplification:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py` (`RunnerConfig.runtime_mode`, runtime-mode normalization/override, startup-sequence bypass, CLI `--runtime-mode`).

Excel input snapshot used for current initialization:
- Workbook: `distillation_column_template.xlsx`
- Sheet: `Initial Conditions`
- Columns: `Stage`, `Liquid Flow (lbmol/h)`, `Liquid Holdup (lbmol)`

Stage liquid-holdup values currently in the model input (intended to align startup holdups with stage liquid traffic):

| Stage | Liquid Flow (lbmol/h) | Liquid Holdup (lbmol) |
|---:|---:|---:|
| 1 | 5952.48 | 0.000000 |
| 2 | 5754.04 | 38.192603 |
| 3 | 5540.83 | 34.514640 |
| 4 | 5352.15 | 33.466311 |
| 5 | 5219.98 | 32.514779 |
| 6 | 5143.75 | 31.891623 |
| 7 | 5104.21 | 31.440346 |
| 8 | 5081.34 | 31.139226 |
| 9 | 5059.77 | 30.907903 |
| 10 | 5025.91 | 30.670352 |
| 11 | 4964.11 | 30.342772 |
| 12 | 15885.10 | 51.062141 |
| 13 | 15921.40 | 50.713991 |
| 14 | 16001.70 | 50.387809 |
| 15 | 16123.70 | 51.827779 |
| 16 | 16269.90 | 62.535311 |
| 17 | 16410.80 | 63.866279 |
| 18 | 16506.90 | 61.999873 |
| 19 | 16505.50 | 60.324372 |
| 20 | 0.00 | 0.000000 |

Observed runtime messages from short verification runs on 2026-02-21:

Command:
`python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo stub --n-steps 1 --dt 0.2 --runtime-mode parity --enable-startup-hydraulic-sequence --no-write-logs --allow-repeat-command`

Key output:
- `[Init] runtime_mode=parity disables startup hydraulic sequencing; using direct mode behavior.`
- `[Init] Runtime mode active: parity`

Command:
`python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --thermo stub --n-steps 1 --dt 0.2 --runtime-mode hydraulic --enable-startup-hydraulic-sequence --no-write-logs --allow-repeat-command`

Key output:
- `[Init] runtime_mode=hydraulic disables startup hydraulic sequencing; using direct mode behavior.`
- `[Init] Runtime mode active: hydraulic`
- `[Warn] hydraulic+energy with condenser-duty-mode=total-condense can be stiff; consider condenser-duty-mode=specified while approaching steady state.`

Recent sequence-enabled runs before simplification path was enforced by mode presets are listed in:
- `docs/experiment_ledger.md` (e.g., run IDs `20260220_211346`, `20260220_211652`, `20260220_212101`, `20260220_212636`).

## A/B Matrix (Updated Holdups, 300 s)

Objective: test whether updated stage liquid holdups removed early hydraulic blow-up behavior.

Compared runs (same case, same thermo, same condenser mode):

1. Parity baseline:
   - `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --runtime-mode parity --thermo table --thermo-table cache\thermo_table.json --include-energy --condenser-duty-mode specified --n-steps 1500 --dt 0.2 --log-every 20 --allow-repeat-command`
   - Outputs: `logs/column_summary_20260221_080401.csv`, `logs/column_profile_20260221_080401.csv`
2. Hydraulic stress case:
   - `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --runtime-mode hydraulic --thermo table --thermo-table cache\thermo_table.json --include-energy --condenser-duty-mode specified --n-steps 1500 --dt 0.2 --log-every 20 --allow-repeat-command`
   - Outputs: `logs/column_summary_20260221_075704.csv`, `logs/column_profile_20260221_075704.csv`

Extracted metrics:

| Metric | Parity (`080401`) | Hydraulic (`075704`) |
|---|---:|---:|
| Max tray mass residual (0..300 s), lbmol/h | 0.10 | 9006.10 |
| Max tray mass residual (0..60 s), lbmol/h | 0.10 | 4870.89 |
| Stage-2 `y_n_Butane` at t=0 | 0.05094 | 0.05094 |
| Stage-2 `y_n_Butane` at t=300 s | 0.19209 | 0.25908 |
| Stage-2 `Delta y_n_Butane` (0->300 s) | +0.14115 | +0.20814 |
| Top pressure PV at t=0, psia | 209.78 | 218.44 |
| Top pressure PV at t=300 s, psia | 219.22 | 345.43 |
| Top pressure PV `Delta P` (0->300 s), psia | +9.43 | +126.99 |

Additional hydraulic-liquid traffic indicator (Francis diagnostic `L_out_hyd`):
- In hydraulic run (`075704`), internal-stage peak `|dL_out_hyd/dt|` reached about `1846 lbmol/h/s` (stage 18 at ~96 s, `4063 -> 11448 lbmol/h` over one log interval).

Interpretation of matrix:
1. Updated holdups are compatible with parity-mode residual closure (near-zero tray residuals).
2. Full hydraulic mode still shows severe early imbalance and pressure escalation despite the holdup update.
3. Therefore, holdup alignment helped parity consistency but did not remove the hydraulic-mode instability mechanism.

## Pressure-Coupling Isolation + Enthalpy Sanity Check

Isolation run to separate pressure-model feedback from energy-vapor closure:

- Command:
  - `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel logs/tmp_pressure_spec_energy_20260221.xlsx --runtime-mode legacy --thermo table --thermo-table cache\thermo_table.json --include-energy --condenser-duty-mode specified --enable-liquid-hydraulic-override --liquid-hydraulic-override-alpha 1.0 --n-steps 1500 --dt 0.2 --log-every 20 --allow-repeat-command`
- Outputs:
  - `logs/column_summary_20260221_101846.csv`
  - `logs/column_profile_20260221_101846.csv`

Isolation outcome (300 s):

| Metric | `legacy` (`Pressure=spec`, `VaporFlow=energy`, hydraulics on) |
|---|---:|
| Max tray mass residual (0..300 s), lbmol/h | 5259.10 |
| Max tray mass residual (0..60 s), lbmol/h | 5020.58 |
| Stage-2 `Delta y_n_Butane` (0->300 s) | +0.18615 |
| Top pressure PV `Delta P` (0->300 s), psia | +9.66 |

Interpretation:
1. Large residuals persist even when pressure is fixed to spec, so pressure coupling is not the only contributor.
2. The extreme top-pressure escalation appears only when hydraulic pressure closure is enabled.
3. This points to a combined issue: baseline hydraulic/energy convective mismatch plus additional amplification from hydraulic pressure feedback.

Enthalpy sanity check:
1. Available ChemSep workbook (`ChemSep Depropanizer results.xls`) does not include direct stage enthalpy columns on `T_P_Flow profiles`; only T/P/flows and duties are listed.
2. Duty-implied latent heat from ChemSep operating point:
   - Condenser: `48.5e6 / 8333.47 = 5819.90 BTU/lbmol`
   - Reboiler: `79.124e6 / 11743.5 = 6737.68 BTU/lbmol`
3. Model t=0 latent heat diagnostics (from profile logs):
   - Stage 2: about `5809-5815 BTU/lbmol`
   - Stage 18/19: about `6423-6485 BTU/lbmol`
4. Conclusion: no evidence of a gross vapor-enthalpy scale error; latent heats are in the expected range and close to condenser duty-implied values. Remaining instability is more consistent with hydraulic-flow/pressure feedback structure than enthalpy bias alone.

Additional sensitivity check (directly testing the vapor-enthalpy hypothesis):

1. Profile-vapor isolation run (no energy-vapor closure term in `V_out`):
   - `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel logs/tmp_pressure_spec_profile_20260221.xlsx --runtime-mode legacy --thermo table --thermo-table cache\thermo_table.json --include-energy --condenser-duty-mode specified --enable-liquid-hydraulic-override --liquid-hydraulic-override-alpha 1.0 --n-steps 1500 --dt 0.2 --log-every 20 --allow-repeat-command`
   - Outputs: `logs/column_summary_20260221_102826.csv`, `logs/column_profile_20260221_102826.csv`
2. Comparison at 300 s (`Pressure=spec`, hydraulics on):
   - `VaporFlow=profile`: max tray residual about `14563.88 lbmol/h`, top-pressure change about `+9.48 psia`
   - `VaporFlow=energy`: max tray residual about `5259.10 lbmol/h`, top-pressure change about `+9.66 psia`
3. Interpretation:
   - Removing energy-vapor closure did not eliminate the instability signal; it increased residual severity in this pressure-fixed configuration.
   - This further weakens the hypothesis that vapor enthalpy values being “too high” are the primary driver of the blow-up.

## Per-Stage Hydraulic-Factor Calibration Trial

Objective: test whether eliminating the remaining `t=0` hydraulic liquid-flow mismatch (tray-by-tray) resolves the dynamic instability.

Implementation:
1. Expanded geometry `System factor` entries from 3 section rows to per-stage rows (`2..20`) in `distillation_column_template.xlsx`.
2. Fitted each stage factor using `t=0` ratio `L_target / L_out_hyd` from open-loop `Pressure=spec`, `VaporFlow=profile`, liquid hydraulics on.

Immediate `t=0` effect:
1. Internal tray hydraulic-flow fit became near-exact:
   - MAE from about `26.24 lbmol/h` to approximately `0`
   - RMSE from about `39.81 lbmol/h` to approximately `0`
2. `t=0` max tray mass residual dropped to near parity (`~0.1 lbmol/h`).

300 s impact summary (per-stage calibration vs previous baseline):

| Case | Max residual 0..60 s (`lbmol/h`) | Max residual 0..300 s (`lbmol/h`) | Top pressure `Delta P` 0->300 s (`psia`) |
|---|---:|---:|---:|
| `legacy spec+profile+hydraulics` before | 11780.49 | 14563.88 | +9.48 |
| `legacy spec+profile+hydraulics` per-stage | 11811.90 | 11811.90 | +9.48 |
| `legacy spec+energy+hydraulics` before | 5020.58 | 5259.10 | +9.66 |
| `legacy spec+energy+hydraulics` per-stage | 5072.15 | 5296.31 | +9.66 |
| `hydraulic runtime` before | 4870.89 | 9006.10 | +126.99 |
| `hydraulic runtime` per-stage | 5020.62 | 9314.45 | +123.29 |

Interpretation:
1. Static initialization alignment can be made exact with per-stage factors.
2. Dynamic instability remains (and can even worsen slightly in some modes), so the dominant remaining issue is not solved by static liquid-factor calibration alone.
3. This reinforces that pressure/vapor/hydraulic dynamic coupling is the primary unresolved mechanism.

## ChemSep PR Enthalpy Cross-Check (Warmer Feed Case)

Objective: confirm whether model vapor/liquid enthalpies at `t=0` materially deviate from ChemSep for the same stage conditions.

Source data:
- Workbook: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\ChemSep Depropanizer_warmer_feed.xls`
- ChemSep enthalpy sheet: `Enthalpies, entropies, entropy` (stage `Hv`, `Hl` in `Btu/lbmol`)

Model comparison setup:
1. Built temp model case from ChemSep stage profiles (`T`, `P`, `L`, `V`, `x`, `y`):
   - `logs/tmp_case_from_chemsep_warmer_feed_20260221.xlsx`
2. Ran one-step parity evaluation with startup thermo conditioning disabled:
   - `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel logs/tmp_case_from_chemsep_warmer_feed_20260221.xlsx --runtime-mode parity --thermo table --thermo-table cache\thermo_table.json --include-energy --disable-startup-thermo-conditioning --n-steps 1 --dt 0.2 --log-every 1 --allow-repeat-command`
   - Outputs: `logs/column_profile_20260221_104202.csv`, `logs/column_summary_20260221_104202.csv`
3. Wrote stage-by-stage comparison artifact:
   - `logs/enthalpy_compare_chemsep_vs_model_t0_20260221.csv`

Summary metrics (`Btu/lbmol`):

| Metric | Value |
|---|---:|
| `Hv` MAE (all stages) | 340.85 |
| `Hv` MAE (excluding stage 1) | 53.63 |
| `Hv` max abs delta (excluding stage 1) | 84.41 |
| `Hl` MAE (all stages) | 72.38 |
| `Hl` max abs delta (all stages) | 244.67 |
| Latent heat (`Hv-Hl`) MAE (excluding stage 1) | 29.89 |
| Latent heat (`Hv-Hl`) MAPE (excluding stage 1) | ~0.47% |

Interpretation:
1. Internal-stage vapor/liquid enthalpies are reasonably close to ChemSep at `t=0`; no large systematic PR enthalpy bias was found.
2. Stage-1 vapor enthalpy is a known outlier in direct comparison because the model enforces a total-condenser boundary (`V_out[1]=0`), so that state is not directly equivalent to ChemSep’s reported vapor enthalpy at stage 1.
3. Largest residual differences are concentrated at boundary stages (notably reboiler-side liquid enthalpy), consistent with boundary-model differences rather than a column-wide enthalpy-model error.

## Pressure/Vapor Feedback Isolation Matrix (Hydraulic Mode, Per-Stage Calibrated Holdups)

Objective: isolate whether pressure-profile feedback or vapor-flow dynamics are the dominant amplifier after the liquid holdup/factor alignment work.

Common setup:
1. `python -m dynamic_distillation.dynamic_run_scaffold_v1 --excel distillation_column_template.xlsx --runtime-mode hydraulic --thermo table --thermo-table cache\thermo_table.json --include-energy --condenser-duty-mode specified --n-steps 1500 --dt 0.2 --log-every 20 --allow-repeat-command`
2. Isolation knobs applied as listed below:
   - Pressure-freeze: `--hydraulic-pressure-relaxation-sec 1e8`
   - Vapor-freeze: `--vapor-flow-relaxation-sec 1e8`
   - Both-freeze: both flags above
3. Comparison artifact: `logs/hydraulic_isolation_matrix_20260221.csv`

Runs:
1. Baseline hydraulic mode: `20260221_120758`
2. Freeze pressure feedback only: `20260221_121857`
3. Freeze vapor-flow dynamics only: `20260221_122721`
4. Freeze both pressure and vapor feedback: `20260221_123434`

Extracted metrics (0..300 s):

| Case | Top pressure `Delta P` (`psia`) | Max tray residual 0..60 s (`lbmol/h`) | Max tray residual 0..300 s (`lbmol/h`) | Peak `|dL_out_hyd/dt|` (`lbmol/h/s`) |
|---|---:|---:|---:|---:|
| Baseline | +123.29 | 5020.62 | 9314.45 | 1851.79 |
| Freeze pressure only | +115.77 | 4919.97 | 9115.84 | 1888.33 |
| Freeze vapor only | +32.89 | 6763.43 | 7998.88 | 1437.68 |
| Freeze pressure + vapor | +33.60 | 6683.16 | 7412.97 | 1384.97 |

Interpretation of isolation matrix:
1. Freezing hydraulic pressure feedback alone gives only a small improvement.
2. Freezing vapor-flow dynamics produces a large reduction in top-pressure escalation and hydraulic-flow slew (`dL_out_hyd/dt`), with a clear reduction in 300 s peak residual.
3. Adding pressure freeze on top of vapor freeze gives only marginal extra benefit, indicating vapor-side dynamic response is the stronger remaining amplifier in the current hydraulic mode.
4. The instability is not fully removed, so additional vapor-hydraulic closure tuning is still required.

## Vapor-Flow Relaxation Tuning Sweep (Hydraulic Mode)

Objective: determine whether the remaining instability can be reduced by tuning vapor-flow dynamics (without changing model structure).

Artifacts:
1. Short-screen and confirmations: `logs/vapor_tuning_sweep_20260221_124926/`
2. Consolidated 300 s ranking: `logs/vapor_tuning_sweep_20260221_124926/confirm_300s_ranked_all.csv`

300 s confirmation summary (default reboiler-neighbor guard unless noted):

| Case | `tau_vflow` (s) | Top pressure `Delta P` (`psia`) | Max tray residual (`lbmol/h`) | Peak `|dL_out_hyd/dt|` (`lbmol/h/s`) |
|---|---:|---:|---:|---:|
| Baseline | default | +123.29 | 9314.45 | 1851.79 |
| Tuned A | 40 | +16.61 | 7976.85 | 1427.56 |
| Tuned B | 80 | +7.54 | 7756.54 | 1408.62 |
| Tuned C | 120 | +10.86 | 7764.29 | 1404.26 |
| Freeze reference | `1e8` | +32.89 | 7998.88 | 1437.68 |

Additional checks:
1. `tau_vflow=5` lowered residual magnitude but caused very large top-pressure escalation (`+237 psia`), so it is not an acceptable operating point.
2. Tightening reboiler-neighbor guard to `1.10/0.90` at `tau_vflow=10` degraded metrics versus default guard.
3. Further tightening to `1.02/0.98` also degraded 300 s behavior in tested cases:
   - default `tau_vflow`: pressure `+123.29 -> +151.44 psia`, residual `9314 -> 10125 lbmol/h`
   - `tau_vflow=10`: pressure `+110.98 -> +145.43 psia`, residual `9030 -> 10013 lbmol/h`

Interpretation:
1. Vapor-flow relaxation is a high-leverage stabilization knob in this model.
2. A practical tuned region exists near `tau_vflow=80..120 s` (with default reboiler-neighbor guard), where pressure escalation and hydraulic slew are strongly reduced while residuals also improve.
3. Residuals are still large versus parity mode, so tuning helps substantially but does not fully close DD-011.

## Rejected Path: Removing `dT` Target Term In Vapor Closure

Test objective: check whether removing previous-step `dT` feed-forward from energy vapor closure enables realistic (`~5..15 s`) vapor-flow relaxation without pressure drift.

Trial commands:
1. `--disable-vapor-flow-dt-target` with default vapor-flow relaxation.
2. `--disable-vapor-flow-dt-target --vapor-flow-relaxation-sec 10`.

Observed outcome (300 s):

| Case | Top pressure `Delta P` (`psia`) | Max tray residual (`lbmol/h`) | Peak `|dL_out_hyd/dt|` (`lbmol/h/s`) |
|---|---:|---:|---:|
| Baseline (`20260221_130923`) | +123.29 | 9314.45 | 1851.79 |
| Disable `dT` target (`20260221_141715`) | +236.20 | 8912.74 | 1522.19 |
| Disable `dT` target + `tau_vflow=10` (`20260221_141111`) | +246.58 | 8521.03 | 1457.26 |

Conclusion:
1. This path reduces some residual/slew metrics but significantly worsens pressure drift.
2. It does not satisfy the stabilization objective and is not recommended as the next development path.

## Top-Drum Pressure-Gate Finding (Physical, High-Impact)

Observation from code path:
1. With the default soft gate (`top_drum_pressure_gate_soft_psi=0.25`), when `dP_stage2_to_top_drum=0`, the gate scale is `0.5`.
2. That allows 50% of computed vapor slip into the top drum at zero driving force.

Hydraulic-mode 300 s A/B (same case, no artificial high `tau_vflow`):

| Case | Top-gate soft width (`psi`) | `V_to_top_drum` at `t=0` (`lbmol/h`) | Top pressure `Delta P` (`psia`) | Max tray residual (`lbmol/h`) |
|---|---:|---:|---:|---:|
| Baseline (`20260221_130923`) | 0.25 | 421.05 | +123.29 | 9314.45 |
| Hard gate (`20260221_144950`) | 0.0 | 0.00 | +25.06 | 9379.49 |
| `tau_vflow=10` + hard gate (`20260221_145638`) | 0.0 | 0.00 | +24.36 | 9222.38 |

Interpretation:
1. Enforcing zero slip at zero pressure driving force is physically reasonable and significantly reduces top-pressure escalation.
2. This improvement does not rely on unrealistic vapor-flow relaxation constants.
3. Remaining tray-residual issues persist and should be addressed separately in vapor/energy closure.

## Interpretation

1. DD-011 root cause remains valid: profile-vs-hydraulics internal flow mismatch is the primary parity-break mechanism.
2. The new runtime presets reduce ambiguity during diagnosis:
   - Use `parity` to test ChemSep-profile consistency without liquid-hydraulic replacement.
   - Use `hydraulic` to stress full dynamic hydraulics with explicit acknowledgment of stiffness risk.
3. Sequencing is now a legacy transitional aid, not part of simplified diagnostic modes.

## Operational Guidance

1. For parity/regression checks, run `--runtime-mode parity`.
2. For hydraulic development tests, run `--runtime-mode hydraulic` and prefer `condenser-duty-mode=specified` during early stabilization.
3. Use `--runtime-mode legacy` only when explicitly evaluating the staged startup-sequencing strategy.

## Open Items

1. Calibrate liquid and vapor hydraulic parameterization so full hydraulic mode reproduces the intended steady operating point (not just transiently stable behavior).
2. Re-run longer hydraulic-mode cases with updated holdup assumptions and track residual trajectories against parity baseline.
3. Decide whether DD-011 should remain a single issue with follow-ups or be split into:
   - liquid-hydraulic calibration
   - vapor-hydraulic/pressure-coupling stabilization
