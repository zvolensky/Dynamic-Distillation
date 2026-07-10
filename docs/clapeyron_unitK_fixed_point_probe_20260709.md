# Clapeyron Unit-K Fixed-Point Probe

Date: 2026-07-09

## Purpose

The unit-K quarantine run showed frequent replacement of fresh thermo packets with older non-unit-K packets. This probe asks whether the fresh unit-K packets are caused by runtime cache/batch plumbing, by the mixed tray composition basis, or by the Clapeyron TP flash behavior at the logged tray states.

## Inputs

- Runtime profile: `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_unitKquarantine_1800s_20260709/column_profile_20260709_194209.csv`
- Workbook seed: `logs/c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Focus stages: `3,4,16,17,18,19`
- Focus times: `300,900,1800 s`
- Composition bases tested: liquid `x`, vapor `y`, and mixed tray `z = (ML*x + MV*y)/(ML+MV)`

## Results

Clapeyron PR:

- Report: `logs/clapeyron_unitK_probe_basis_all_focus_20260709.md`
- Records: `54`
- Errors: `0`
- Fresh scalar-object unit-K records: `40/54`
- Fresh tuple-call unit-K records: `40/54`
- Fresh batch unit-K records: `40/54`
- Batch and scalar agreed to roundoff: max `|batch - scalar K| = 5.33e-15`

DWSIM PR comparison:

- DWSIM path used: `C:\Users\Thomas Zvolensky\AppData\Local\DWSIM`
- Report: `logs/dwsim_vs_clapeyron_pr_unitK_probe_focus_20260709.md`
- Records: `54`
- Errors: `0`
- Clapeyron PR fresh scalar unit-K records: `40/54`
- DWSIM PR unit-K records: `0/54`
- Maximum `|DWSIM K - Clapeyron K|`: `0.91569`
- By basis:
  - `x`: Clapeyron unit-K `13/18`; DWSIM unit-K `0/18`
  - `y`: Clapeyron unit-K `13/18`; DWSIM unit-K `0/18`
  - `z`: Clapeyron unit-K `14/18`; DWSIM unit-K `0/18`

Clapeyron SRK control:

- Report: `logs/clapeyron_srk_unitK_probe_basis_all_focus_20260709.md`
- Records: `54`
- Errors: `0`
- Fresh scalar-object unit-K records: `41/54`
- Fresh tuple-call unit-K records: `41/54`
- Fresh batch unit-K records: `41/54`
- Batch and scalar agreed closely: max `|batch - scalar K| = 2.51e-10`

## Interpretation

The current evidence points away from a runtime cache bug or a batch-flash bug:

- scalar, tuple, and batch calls produce the same unit-K outcome;
- unit-K appears across liquid, vapor, and mixed composition bases;
- SRK behaves almost the same as PR at these fixed points.
- DWSIM PR does not reproduce the unit-K result at the same `T/P/composition` points.

That means the quarantine is not correcting an accidental transport artifact. It is shielding the dynamic run from a fresh Clapeyron TP flash result that is repeatedly degenerate at the logged states, while DWSIM PR sees physically differentiated K-values at those same states.

## Local Setup Note

The DWSIM PR fixed-point comparison required:

- installing `pythonnet`;
- setting `DWSIM_DTL_PATH=C:\Users\Thomas Zvolensky\AppData\Local\DWSIM`.

The installed DWSIM folder does not use the older standalone-library-only layout, but `pr_flash_backend_v1` can initialize successfully against `DWSIM.Thermodynamics.dll` in this folder.

## Recommended Next Step

Do not treat the current Clapeyron TP flash result as an acceptable runtime equilibrium target for this C3/C4 case. The next implementation branch should either:

- run the C3/C4 dynamic case with DWSIM PR as the primary thermo backend for comparison, or
- modify the Clapeyron adapter/flash selection so it reproduces DWSIM-like non-unit K-values at these fixed points before using it in long dynamic runs.

## 2026-07-10 Dynamic Follow-Up

The DWSIM PR dynamic comparison has now been run.

Run:

- `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_dwsimPR_900s_r2_20260710`

Result:

- final time: `900 s`
- steady-state flag: `1`
- steady-state score: `0.3539`
- max relative state rate: `0.001062 1/s`
- sim/wall ratio: `0.478 sim-s/wall-s`

The DWSIM PR run did not reproduce the low-overhead collapse seen in the Clapeyron unit-K quarantine run. It retained physically plausible overhead vapor traffic and a feasible reflux/distillate balance.

Current conclusion: Clapeyron is off the validation path for this C3/C4 case until the adapter or flash strategy is repaired. DWSIM PR is the reference backend for continued model validation.
