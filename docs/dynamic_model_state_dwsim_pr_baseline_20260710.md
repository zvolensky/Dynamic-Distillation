# Dynamic Model State: DWSIM PR Baseline

Date: 2026-07-10

## Summary

The C3/C4 model failure previously attributed to possible model-equation instability is now primarily traced to the Clapeyron thermo backend as used by this codebase.

The current conclusion is:

- Clapeyron PR/SRK TP flash is not acceptable for this C3/C4 dynamic run path because it returns degenerate unit-K packets at many live tray states.
- DWSIM PR returns non-unit K-values at the same fixed `T/P/composition` points.
- With DWSIM PR as the primary thermo backend, the same Q42 fixed-condenser-duty, true-level-control, partial-liquid-hydraulic recipe runs to 900 s and passes the rate-based dynamic steady-state detector.
- The model should be treated as credible enough for continued validation under DWSIM PR, but not yet fully validated.

## Key Evidence

### Fixed-Point Thermo Probe

Report:

- `logs/dwsim_vs_clapeyron_pr_unitK_probe_focus_20260709.md`

Results:

- Clapeyron PR unit-K records: `40/54`
- DWSIM PR unit-K records: `0/54`
- Maximum `|DWSIM K - Clapeyron K|`: `0.91569`

This comparison used the same logged tray states, times, and composition bases:

- stages: `3,4,16,17,18,19`
- times: `300,900,1800 s`
- bases: liquid `x`, vapor `y`, and mixed tray `z`

### DWSIM PR Dynamic Run

Run:

- `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_dwsimPR_900s_r2_20260710`

Final metrics:

- final time: `900 s`
- elapsed wall time: `1881.14 s`
- sim/wall ratio: `0.478 sim-s/wall-s`
- steady-state flag: `1`
- steady-state score: `0.3539`
- max relative state rate: `0.001062 1/s`

Final operating values:

- top drum pressure: `228.16 psia`
- condenser duty used: `-42.000 MMBtu/h`
- condenser duty calculated: `-47.592 MMBtu/h`
- reboiler duty used: `54.844 MMBtu/h`
- overhead vapor condensed: `7841.57 lbmol/h`
- reflux: `5967.32 lbmol/h`
- distillate: `2308.26 lbmol/h`
- bottoms: `4305.44 lbmol/h`

Top boundary behavior is physically plausible:

- condensate is large enough to supply reflux plus distillate;
- reflux/distillate ratio is about `2.58`;
- the prior Clapeyron-unit-K low-overhead collapse is not reproduced.

The prior stage 17-to-16 vapor cliff is also not reproduced. Final vapor traffic is smooth enough for diagnostic purposes:

- stage 16 `V_out = 7563.72 lbmol/h`
- stage 17 `V_out = 7597.89 lbmol/h`
- stage 18 `V_out = 7719.76 lbmol/h`
- stage 19 `V_out = 7794.14 lbmol/h`
- stage 20 `V_out = 8030.03 lbmol/h`

## Current Interpretation

The model is not proven perfect, but the evidence no longer supports treating the dynamic equations as fundamentally broken.

The better statement is:

> The C3/C4 dynamic model behaves credibly under DWSIM PR. The major recent failure mode was Clapeyron thermo backend behavior, not a generic model-equation failure.

## Remaining Caveats

The following still need validation:

- compare final DWSIM PR products, levels, duties, and profiles against the Excel/ChemSep reference;
- run longer than 900 s or run a disturbance test;
- decide whether bottoms level being below SP is a controller/tuning issue, operating-point issue, or remaining model issue;
- retire or repair Clapeyron usage before using it for this C3/C4 validation path.

## Recommendation

Use DWSIM PR as the reference thermo backend for this C3/C4 model-development path.

Keep Clapeyron available only as an experimental backend until its fixed-point K-values can be made consistent with DWSIM PR or another trusted reference for the same `T/P/composition` states.
