# DD-011 Follow-up: Runtime Simplification And Hydraulics Findings

Date: 2026-02-21 (local)
Status addendum: 2026-02-27 (local)
Related root-cause report: `docs/dd_011_hydraulic_parity_drift_report_2026-02-19.md`

Historical note (2026-03-28):
This follow-up remains useful as a record of the original DD-011 runtime-simplification and hydraulic-parity work, but it no longer reflects the current stabilized baseline. Since this note:
1. The true-level hydraulic branch reached a stable `600 s` run (`20260328_145436`) after fixing the stage-1 condenser thermal closure.
2. The stage-10 equilibrium-relaxation trigger was materially reduced by selective live-PR use in the eq-relax flash path.
3. The standard explicit-sump model was corrected so the reboiler is sump-fed.

For current status and active issues, use [issue_log.md](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/issue_log.md) rather than this document alone.

## Purpose

Document findings collected after the 2026-02-19 DD-011 root-cause write-up and record the implemented simplification path for ongoing diagnostics.

## Executive Summary (2026-02-23)

This section is the current decision snapshot for DD-011.

Current status:
1. The model no longer exhibits immediate startup blow-up in the corrected overhead-capacitance case, but it is not stable enough for parity-grade dynamic confidence.
2. The dominant off-course behavior develops after startup, concentrated around stages 16-18 in the `~90-112 s` window.
3. Pressure control using condenser duty is functional but shows late high-frequency chatter that amplifies drift.

Most recent evidence run:
1. Case: `distillation_column_template_overhead_caps.xlsx`
2. Run: `legacy`, `dt=0.2 s`, `300 s`, `log-every=1`, level + pressure + distillate composition + bottoms composition ON.
3. Artifacts:
   - `logs/overhead_totalcond_ctrl_on/column_summary_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/column_profile_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/overall_derivative_metrics_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/stage_derivative_metrics_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/startup_t_p_l_v_ml_mv_derivatives_20260223_133146.csv`

Key numbers:
1. Max tray mass residual (0..300 s): `7263.26 lbmol/h` (stage 18, `t~94.6 s`).
2. Top pressure drift: `220.44 -> 236.92 psia` (`+16.48 psia` in 300 s).
3. Peak hydraulic-rate derivatives:
   - `|dL_out_hyd/dt|`: `2818.70 lbmol/h/s` (stage 16, `t~89.4 s`)
   - `|dV_out/dt|`: `334.66 lbmol/h/s` (stage 18, `t~112.2 s`)
4. Startup derivatives are elevated but moderate on a relative basis:
   - `t=0.0 s` max `|dL/dt|=819.84`, max `|dV/dt|=129.13`
   - startup relative change (`0.0->0.2 s`): liquid max about `1.01%`, vapor max about `0.34%`

Interpretation:
1. Startup mismatch is no longer the primary failure signal.
2. Main instability driver is mid-run hydraulic acceleration (stages 16-18), with pressure-MV chatter as a secondary amplifier.
3. Controllers contribute to drift but are not the sole root cause.
4. Startup hydraulic sequencing was tested historically, but not yet re-tested apples-to-apples on the corrected 2026-02-23 case and current pressure-gain sign convention.

Immediate next actions:
1. Run a strict A/B startup-sequence test on `distillation_column_template_overhead_caps.xlsx` with identical controller settings and only sequence toggled.
2. Dampen pressure-loop chatter using PV filtering and MV slew limits while preserving pressure authority.
3. Run focused sensitivity around stages 16-18 (vapor/liquid capacitance and hydraulic parameters) and rank by reduction in `max |dL/dt|`, `max |dV/dt|`, and 300 s residual.

## Current State Update (2026-02-26, Bottoms-MV Comparison And C3 K Diagnostics)

Objective: document what changed when the bottoms-composition manipulated variable was switched from `boilup` to `reboiler-duty` and reconcile the C3 K-value interpretation.

Compared 300 s hydraulic runs (`dt=0.2 s`, table thermo, energy ON):

1. `--bottoms-comp-mv boilup`
   - `logs/column_summary_20260226_184354.csv`
   - `logs/column_profile_20260226_184354.csv`
2. `--bottoms-comp-mv reboiler-duty`
   - `logs/column_summary_20260226_193355.csv`
   - `logs/column_profile_20260226_193355.csv`
   - `logs/stage19_xc3_vs_time_20260226_193355.csv`
   - `logs/stage19_kc3_vs_time_20260226_193355.csv`

Observed outcomes:

1. In `boilup` MV mode (`20260226_184354`), `Boilup_cmd` moved (`8036.48 -> 8472.96 lbmol/h`) while `Q_reb_used` remained fixed (`54.706 MMBtu/h`).
2. In `reboiler-duty` MV mode (`20260226_193355`), `Q_reb_cmd=Q_reb_used` moved (`54.706 -> 58.135 MMBtu/h`) and `Boilup_cmd_lbmolph` is intentionally `NaN`.
3. Despite higher reboiler duty, lower-stage vapor traffic decreased in `20260226_193355`:
   - stage-20 `V_out`: `8233 -> 6468 lbmol/h`
   - stage-19 `V_out`: `8019 -> 6491 lbmol/h`
4. Stage-19 propane liquid composition increased:
   - `xC3`: `0.06805` at `t=0`, peak `0.18788` at `t=106 s`, final `0.14684`.
5. Product specs remained off target at 300 s:
   - `xD_C4`: `0.16301` (SP `0.09400`)
   - `xB_C3`: `0.08429` (SP `0.04700`)
   - steady-state detector: `flag=0`, `score=208.19`.

K-value interpretation update (stage 19, C3):

1. `K_thermo_C3` is the flash-equilibrium K at tray `T,P,z`; it stayed in `1.869..1.971`.
2. `K_state_C3` is dynamic-state `y/x`; final value was `1.40299`.
3. `K_state_over_K_thermo_C3` indicates disequilibrium; final ratio was `0.74699`.
4. Therefore, the latest run does not indicate a gross C3 thermo-K magnitude error at stage 19; it indicates the dynamic state remains significantly off equilibrium.

## New Findings

1. The runner now has explicit runtime behavior modes:
   - `parity`: force `Pressure=spec`, `VaporFlow=profile`, liquid-hydraulic override off.
   - `hydraulic`: force `Pressure=hydraulic`, `VaporFlow=energy`, liquid-hydraulic override on.
   - `legacy`: preserve prior spec/CLI-driven behavior.
2. Startup hydraulic sequencing is now intentionally bypassed in both simplified modes (`parity`, `hydraulic`) and remains applicable only in `legacy`.
3. The simplified modes make parity diagnostics deterministic by removing hidden startup-mode transitions.
4. Hydraulic+energy startup remains numerically stiff in short checks; the runner emits an explicit warning under `hydraulic` mode with `condenser-duty-mode=total-condense`.
5. Current pressure-capacitance input now reads from Excel keys:
   - `Overhead Vapor Line Volume (ft3)`
   - `Condenser Vapor Volume (ft3)`
6. For `Condenser Type = Total`, distillate-drum vapor space is excluded from pressure-side column capacitance; only overhead line + condenser vapor space are included.
7. Verified on current case: `V_top_drum_vapor_ft3 = 156` for `56 ft3` overhead line + `100 ft3` condenser vapor volume.
8. Startup hydraulic sequencing was tested previously, but those sequence runs used older workbook/sign settings and were not an apples-to-apples retest of the corrected 2026-02-23 case.

## Evidence Snapshot

Code paths implementing the simplification:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py` (`RunnerConfig.runtime_mode`, runtime-mode normalization/override, startup-sequence bypass, CLI `--runtime-mode`).

Excel input snapshot used for the original 2026-02-21 baseline:
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

## Current State Update (2026-02-23, Corrected Overhead-Capacitance Case)

Latest high-resolution run:

1. Case/workbook: `distillation_column_template_overhead_caps.xlsx`
2. Runtime: `legacy`, `dt=0.2 s`, `300 s`, `log-every=1`
3. Controllers ON: level + pressure (`MV=condenser-duty`) + distillate composition + bottoms composition
4. Logs:
   - `logs/overhead_totalcond_ctrl_on/column_summary_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/column_profile_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/overall_derivative_metrics_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/stage_derivative_metrics_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/startup_t_p_l_v_ml_mv_derivatives_20260223_133146.csv`

Key metrics (0..300 s):

| Metric | Value |
|---|---:|
| Max tray mass residual (`lbmol/h`) | `7263.26` (stage 18, `t~94.6 s`) |
| Max tray mass residual 0..60 s (`lbmol/h`) | `4456.20` (stage 18, `t~34.2 s`) |
| Top pressure drift (`psia`) | `220.44 -> 236.92` (`+16.48`) |
| Distillate C4 PV drift (`mol frac`) | `0.14689 -> 0.18408` (SP `0.09513`) |
| Bottoms C3 PV drift (`mol frac`) | `0.04514 -> 0.07078` (SP `0.04757`) |
| Peak `|dL_out_hyd/dt|` (`lbmol/h/s`) | `2818.70` (stage 16, `t~89.4 s`) |
| Peak `|dV_out/dt|` (`lbmol/h/s`) | `334.66` (stage 18, `t~112.2 s`) |
| Peak `|dP/dt|` (`psia/s`) | `4.092` (stage 19/20, `t~291.4 s`) |

Startup derivative check (`forward dt=0.2 s`):

| Time (`s`) | Max `|dL/dt|` (`lbmol/h/s`) | Stage | Max `|dV/dt|` (`lbmol/h/s`) | Stage |
|---:|---:|---:|---:|---:|
| 0.0 | 819.84 | 19 | 129.13 | 12 |
| 0.2 | 775.16 | 19 | 126.98 | 12 |
| 0.4 | 729.12 | 19 | 124.87 | 12 |

Startup relative flow change (`0.0 -> 0.2 s`) is modest:
1. Liquid max relative change about `1.01%` (stage 19).
2. Vapor max relative change about `0.34%` (stage 12).

Late pressure-MV chatter indicator (`290..300 s`):
1. `P_top_ctrl_pv` range: `236.62..238.12 psia`.
2. `Q_cond_cmd` range: `-54.19..-50.79 MMBtu/h`.

Interpretation update:
1. In the corrected case, startup derivatives are not the dominant instability driver.
2. The main divergence develops later in the internal hydraulic zone (stages 16-18, ~90-112 s).
3. Pressure-loop/condenser-duty chatter is a late amplifier.
4. Controllers contribute to off-course behavior, but they are not the sole root mechanism.

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

## Conductance-Mode Follow-Up (Pressure-Flow Prototype)

Objective: test whether a pressure-conductance vapor-flow closure can replace the energy-based `V_out` closure without catastrophic pressure escalation.

Implementation notes:
1. Added `vapor_flow_model="conductance"` path in `column_rhs` and scaffold validation/input normalization.
2. Initial conductance runs (`20260221_152752`, `20260221_153331`) were unstable under full hydraulic coupling.
3. Additional stabilization test disabled vapor-holdup relaxation (`--vapor-holdup-relaxation-sec 0`) but still showed long-horizon runaway before code fix (`20260221_155309`).
4. Updated top-gate blocked-vapor handling for conductance mode in `src/dynamic_distillation/column_rhs_v1.py`:
   - old behavior: blocked slip was forced into `V_condensed_in` (instantaneous extra condensation),
   - new behavior (conductance mode only): blocked slip reduces stage-2 vapor outflow (`V_out[2]`), applying back-pressure at the source.
5. Added regression test:
   - `tests/test_column_rhs_v1.py::test_top_drum_pressure_gate_conductance_reduces_stage2_vapor_outflow`.

Comparison artifact:
- `logs/conductance_mode_ab_20260221_post_gate_fix.csv`

Key 300 s results:

| Case | Run ID | Top pressure `Delta P` (`psia`) | Max tray residual 0..300 s (`lbmol/h`) | Final Distillate holdup (`lbmol`) |
|---|---|---:|---:|---:|
| Conductance default gate (pre) | `20260221_152752` | `+4.18e9` | `8.92e233` | `2822.81` |
| Conductance hard gate + `tau_vflow=10` (pre) | `20260221_153331` | `-218.39` | `5.93e257` | `11803.01` |
| Conductance hard gate + `tau_vflow=10` + `tau_v=0` (pre-patch) | `20260221_155309` | `+5.32e5` | `2.83e6` | `40688.58` |
| Conductance hard gate + `tau_vflow=10` + `tau_v=0` (post-patch) | `20260221_160831` | `+10.81` | `27775.54` | `1285.85` |

Interpretation:
1. The conductance source-coupling fix removed catastrophic top-pressure runaway in the tested 300 s case.
2. Global mass closure remained near machine precision (order `1e-2 lbmol/h`) in both pre/post patched runs.
3. Tray residuals are still materially above parity/hydraulic baseline targets, so conductance closure is now bounded but not yet parity-grade.

Additional cap refinement (same day):
1. Added a conductance clamp refinement so internal vapor-flow upper limits are constrained by both:
   - previous-step growth bound, and
   - nominal-profile absolute cap (`1.5 * V_profile`), when profile data are available.
2. This prevents previous-step ratcheting from allowing long-horizon drift above profile scale.
3. Regression test added:
   - `tests/test_column_rhs_v1.py::test_vapor_flow_conductance_caps_to_nominal_when_prev_is_high`

New 300 s result after cap refinement:

| Case | Run ID | Top pressure `Delta P` (`psia`) | Max tray residual 0..60 s (`lbmol/h`) | Max tray residual 0..300 s (`lbmol/h`) |
|---|---|---:|---:|---:|
| Conductance + hard gate + `tau_vflow=10` + `tau_v=0` (post gate-fix only) | `20260221_160831` | `+10.81` | `27775.54` | `27775.54` |
| Conductance + hard gate + `tau_vflow=10` + `tau_v=0` (post gate+cap refinement) | `20260221_165045` | `-5.98` | `19331.91` | `19992.47` |
| Conductance + hard gate + `tau_vflow=10` + `tau_v=0` + nominal-hi ratio `1.1` | `20260221_171049` | `-8.59` | `12331.41` | `14537.15` |

Updated comparison artifact:
- `logs/conductance_mode_ab_20260221_cap_fix.csv`

Interpretation update:
1. Cap refinement further reduced conductance residual magnitude (about 28% reduction in 300 s max residual vs post gate-fix only).
2. Pressure remains bounded over 300 s without artificial `tau_vflow` in the 80-120 s range.
3. Tightening the nominal cap from default (`1.5`) to `1.1` in a full 300 s run reduced 300 s max tray residual by another ~27% (`19992.47 -> 14537.15 lbmol/h`) while remaining bounded.
4. Conductance mode still does not reach parity residual levels, but the failure mode has shifted from blow-up to bounded mismatch.

Composition-control check (same hydraulics, 300 s):
1. Baseline (no composition loop): `20260221_171049`
2. Distillate C4 composition loop enabled (`x_SP=0.050938`, `Kc=500`, `Ti=600 s`, reflux MV): `20260221_172535`

| Case | Run ID | Top pressure `Delta P` (`psia`) | Max tray residual 0..300 s (`lbmol/h`) | `Distillate_x_n_Butane` at 300 s | `x_Distillate_n_Butane` at 300 s |
|---|---|---:|---:|---:|---:|
| No distillate composition control | `20260221_171049` | `-8.59` | `14537.15` | `0.10048` | `0.17500` |
| Distillate composition control enabled | `20260221_172535` | `+2.08` | `18258.96` | `0.10281` | `0.21107` |

Notes:
1. In this scaffold, distillate composition PI uses top-drum liquid composition (`Distillate_x_*`) as PV.
2. Over this 300 s window, enabling the distillate composition loop did not improve C4 behavior for this operating case.

Extended controller A/B (same hydraulics, 300 s):
1. Added full-stack tests with level + pressure + distillate composition.
2. Distillate composition setpoint aligned to controller PV at `t=0`: `x_SP=0.057907`.
3. Reflux-feasibility-cap sensitivity was tested because cap-on behavior reduced reflux when C4 increased.

| Case | Run ID | `P_top Delta` (`psia`) | `Distillate_x_n_Butane` at 300 s | `x_Distillate_n_Butane` at 300 s | Max tray residual 0..300 s (`lbmol/h`) |
|---|---|---:|---:|---:|---:|
| Control off | `20260221_171049` | `-8.59` | `0.10048` | `0.17500` | `14537.15` |
| Level + pressure + xD control, cap ON (`Kc=500`, `Ti=600`) | `20260221_175133` | `+1.99` | `0.10425` | `0.22850` | `17281.04` |
| Level + pressure + xD control, cap OFF (`Kc=500`, `Ti=600`) | `20260221_175912` | `+1.41` | `0.10023` | `0.19168` | `15678.07` |
| Level + pressure + xD control, cap OFF (`Kc=5000`, `Ti=240`) | `20260221_180607` | `+2.87` | `0.10014` | `0.18812` | `15674.32` |

Interpretation (controller A/B):
1. The reflux-feasibility cap materially constrained the distillate composition loop in this case.
2. Disabling the cap restored expected reflux directionality and improved composition behavior versus cap-on runs.
3. Even with stronger `Kc`, distillate C4 remained near the control-off trajectory over 300 s; composition control did not yet deliver a clear improvement.

Controller A/B artifact:
- `logs/controller_ab_20260221.csv`

ChemSep warmer-feed input realignment (late update):
1. The active hydraulic test workbook (`logs/tmp_pressure_hydraulic_conductance_20260221_152741.xlsx`) was re-aligned to:
   - `ChemSep Depropanizer_warmer_feed.xls` stage profiles (`T`, `P`, `L`, `V`, `x`, `y`).
2. Verification after patching showed profile parity at machine precision:
   - `max_abs_dT=0`, `max_abs_dP=0`, `max_abs_dL_finite=0`, `max_abs_dV_finite=0`,
   - `max_abs_dx_row~5.6e-17`, `max_abs_dy_row~5.6e-17`.
3. Distillate composition setpoint was aligned to ChemSep target:
   - `Distillate Composition SP = 0.0951`.
4. Loader update:
   - `src/dynamic_distillation/excel_case_loader_v1.py` now persists `Distillate Composition SP` and `Bottoms Composition SP` from Excel specs, so CLI overrides are no longer required just to use these sheet values.

600 s full-dynamic composition-control check (corrected ChemSep-aligned input, `xD_SP=0.0951`):
1. Both runs used the same dynamic stack (`legacy`, conductance-cap `1.1`, level+pressure+distillate-composition control), with only reflux-feasibility-cap toggled.

| Case | Run ID | `P_top Delta` (`psia`) | `Distillate_x_n_Butane` start -> 600 s | `x_Distillate_n_Butane` start -> 600 s | Max tray residual 0..600 s (`lbmol/h`) |
|---|---|---:|---:|---:|---:|
| Reflux feasibility cap ON | `20260221_185207` | `-0.63` | `0.13543 -> 0.28029` | `0.09513 -> 0.49080` | `16918.18` |
| Reflux feasibility cap OFF | `20260221_190448` | `+9.44` | `0.13543 -> 0.22376` | `0.09513 -> 0.42625` | `14956.53` |

Interpretation (600 s, corrected input):
1. Correcting initialization and setpoint alignment did not eliminate long-horizon composition drift in full dynamic mode.
2. Cap OFF improved composition/residual behavior versus cap ON, but worsened top-pressure drift.
3. The remaining problem appears structural/coupling-dominant rather than a simple setpoint mismatch.

Controller 600 s artifact:
- `logs/controller_ab_20260221_600s.csv`

## Interpretation

1. DD-011 root cause remains valid: profile-vs-hydraulics internal flow mismatch is the primary parity-break mechanism.
2. The new runtime presets reduce ambiguity during diagnosis:
   - Use `parity` to test ChemSep-profile consistency without liquid-hydraulic replacement.
   - Use `hydraulic` to stress full dynamic hydraulics with explicit acknowledgment of stiffness risk.
3. Sequencing is now a legacy transitional aid, not part of simplified diagnostic modes.
4. With corrected ChemSep alignment and updated pressure-side vapor capacitance, the model is improved from prior blow-up cases but still shows material mid-run hydraulic acceleration and composition drift.
5. Current evidence points to stage 16-18 hydraulic acceleration plus late pressure-MV chatter as the highest-impact stabilization targets.

## Operational Guidance

1. For parity/regression checks, run `--runtime-mode parity`.
2. For hydraulic development tests, run `--runtime-mode hydraulic` and prefer `condenser-duty-mode=specified` during early stabilization.
3. Use `--runtime-mode legacy` only when explicitly evaluating the staged startup-sequencing strategy.

## Open Items

1. Run an apples-to-apples startup-sequence A/B on the corrected 2026-02-23 case:
   - same workbook (`distillation_column_template_overhead_caps.xlsx`), same controller stack, same pressure gain sign convention.
2. Dampen pressure-loop chatter while preserving control authority:
   - evaluate PV filter and MV slew settings against `Q_cond` high-frequency switching.
3. Target stage-16..18 hydraulic acceleration directly:
   - test vapor/liquid capacitance and hydraulic-parameter sensitivity focused on that section.
4. Re-run longer hydraulic-mode cases with updated assumptions and track residual trajectories against parity baseline.
5. Decide whether DD-011 should remain a single issue with follow-ups or be split into:
   - liquid-hydraulic calibration
   - vapor-hydraulic/pressure-coupling stabilization
