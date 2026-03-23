# Huang Hybrid Progress

Date: 2026-03-20

Status:
- A Huang-inspired hybrid step has been implemented in the mini8 sequential UV sandbox.
- New mode: `--liquid-flow-mode huang-htc`
- Purpose: replace Francis liquid hydraulics with a hydraulic-time-constant (HTC) tray liquid closure while keeping the rest of the partitioned UV sandbox intact.

Implementation:
- File: `src/dynamic_distillation/uv_flash_sandbox_v1.py`
- Added:
  - `huang_liquid_htc_sec` to `UvMini8PrototypeSpec`
  - `_compute_huang_htc_liquid_flow_closure(...)`
  - CLI support for `--liquid-flow-mode huang-htc`

Current interpretation:
- This is a partial Huang-inspired application.
- Applied:
  - liquid dynamics from tray holdup divided by hydraulic time constant
- Not yet applied:
  - Huang-style pressure update from vapor-phase mass balance in the larger column model

Verification:
- Unit tests passed after the change.

Short mini8 A/B:
- Baseline:
  - `liquid-flow-mode=francis`
  - `vapor-flow-mode=conductance`
  - run id `20260320_133003`
- Huang hybrid:
  - `liquid-flow-mode=huang-htc`
  - `vapor-flow-mode=conductance`
  - run id `20260320_133007`

Artifacts:
- Baseline summary: `sandbox/mini8/runs/uv_flash_summary_20260320_133003.csv`
- Baseline metrics: `sandbox/mini8/runs/uv_flash_compare_metrics_20260320_133003.csv`
- Huang summary: `sandbox/mini8/runs/uv_flash_summary_20260320_133007.csv`
- Huang metrics: `sandbox/mini8/runs/uv_flash_compare_metrics_20260320_133007.csv`

Observed result:
- The first short `4 s` mini8 A/B did not improve parity with `huang-htc`.
- Examples:
  - stage 5 temperature max diff worsened from about `3.53 F` to about `4.04 F`
  - stage 6 temperature max diff worsened from about `3.51 F` to about `3.70 F`
  - bottoms-sump holdup max diff worsened from about `1.83 lbmol` to about `6.38 lbmol`

Conclusion:
- The Huang-inspired HTC liquid closure is now available and clearly marked in the repo.
- It is a valid bridge experiment, but in its first short mini8 form it is not yet a performance or parity improvement over the existing Francis closure.
- Next likely direction, if this branch is continued:
  - add a pressure-side Huang-style update in the main partitioned model, rather than judging Huang solely from the liquid HTC piece by itself.

Later main-model checkpoint:
- That pressure-side Huang work was continued in the main runner after this mini8 note.
- Important outcome:
  - an older top-anchored 20-stage Huang branch was found to be physically invalid because it flattened the tray pressure profile
  - the corrected branch now keeps Huang tray pressure on the free hydraulic tray profile unless an explicit top anchor is provided
- Corrected larger-case result:
  - the 20-stage Huang branch reaches `steady_state_flag = 1` by `900 s`
  - the final tray pressure profile is physically graded again
- Recommended derived workbook for new 20-stage Huang studies:
  - `sandbox/mini8/input/distillation_column_template_20stage_huang_freep_900s_seed.xlsx`
- See:
  - `docs/huang_hybrid_main_model_2026-03-20.md`
