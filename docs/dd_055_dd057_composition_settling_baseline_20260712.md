# DD-055 Through DD-058 Composition-Settling Baseline

Date: 2026-07-12

## Purpose

After DD-054 showed that the lower-column composition front had passed its peak, four more unchanged `300 s` continuations were run. No controller tuning, duty-bias change, hydraulic change, or equation change was introduced. The purpose was to let the column composition settle naturally and determine whether the earlier wave was a transient or renewed instability.

## Results

| Run | Score | Top pressure (psia) | Qcond (MMBtu/h) | Distillate (lbmol/h) | Top level (%) | Bottom level (%) | xD n-C4 | xB n-C4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DD-055 | 0.324 | 222.218 | -50.157 | 2218.65 | 52.082 | 48.623 | 0.063959 | 0.764301 |
| DD-056 | 0.210 | 221.917 | -49.836 | 2304.70 | 51.997 | 48.489 | 0.063796 | 0.747913 |
| DD-057 | 0.133 | 221.732 | -49.362 | 2258.70 | 51.945 | 49.025 | 0.063718 | 0.735688 |
| DD-058 | 0.0848 | 221.871 | -49.163 | 2254.42 | 51.967 | 49.842 | 0.063691 | 0.727823 |

The score decreased on every valid continuation: `2.506 -> 0.420 -> 0.324 -> 0.210 -> 0.133 -> 0.0848` from DD-053 through DD-058. DD-058's final global mass-closure error was `-2.22e-12 lbmol/h`.

## DD-058 endpoint assessment

- Top pressure remained calm at `221.871 psia`; its final-minute trend was `+0.0178 psi/min`.
- Top level was essentially exactly at setpoint (`51.9666%` versus `51.9668%`).
- Bottom level had recovered slightly above setpoint (`49.842%` versus `49.438%`) and was still moving upward slowly.
- Distillate n-butane was `0.06369`, substantially below the ChemSep comparison value of about `0.11`, with a final-minute slope of only `-2.55e-6 mole fraction/min`.
- Bottoms n-butane was still changing at about `-0.00129 mole fraction/min`. This is about `38%` slower than DD-057's final-minute slope, confirming asymptotic settling rather than a renewed wave.
- The corrected normalized equilibrium gate passed with final interior maximum `|y-y_target|=0.00537`, below the `0.01` limit.
- The live vapor-material audit reported a maximum interior relative RHS of `0.000199/s`.

## Decision

DD-058 is the current accepted continuation baseline. It is operationally calm and suitable for restart or subsequent controlled experiments, but it must not be described as an exact steady state because the bottom composition is still asymptotically settling.

No further unchanged continuation is required merely to establish model health or overhead-product quality. A longer hold is appropriate only when a tighter final bottoms-composition value is needed. Any future continuation should start from the valid DD-058 `r2` native checkpoint so controller and runtime memory are preserved.

## Invalid DD-058 attempt

The first folder without the `r2` suffix is invalid evidence. Its shell did not define `DWSIM_DTL_PATH` or add the DWSIM install directory to `PATH`; every requested DWSIM flash failed, the runner retained cached thermo packets, and the trajectory diverged. The corrected `r2` run used the live DWSIM bridge. This exposed a separate fail-fast requirement: a run explicitly requesting DWSIM should abort when the backend is unavailable instead of silently marching on cached packets.

## Artifacts

- `logs/c3c4_dd057_final_composition_settle_hold300s_20260712/run_report_20260712_105152.docx`
- `logs/c3c4_dd057_final_composition_settle_hold300s_20260712/normalized_equilibrium_target_audit.md`
- `logs/c3c4_dd057_final_composition_settle_hold300s_20260712/vapor_rhs_material_terms_audit.md`
- `logs/c3c4_dd057_final_composition_settle_hold300s_20260712/c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_20260712_105152.npz`
- `logs/c3c4_dd058_extended_composition_settle_hold300s_r2_20260712/run_report_20260712_110933.docx`
- `logs/c3c4_dd058_extended_composition_settle_hold300s_r2_20260712/normalized_equilibrium_target_audit.md`
- `logs/c3c4_dd058_extended_composition_settle_hold300s_r2_20260712/vapor_rhs_material_terms_audit.md`
- `logs/c3c4_dd058_extended_composition_settle_hold300s_r2_20260712/c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_20260712_110933.npz`
