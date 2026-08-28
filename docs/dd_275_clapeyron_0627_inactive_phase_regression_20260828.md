# DD-275 Clapeyron 0.6.27 Inactive-Phase Regression

## Decision

Clapeyron 0.6.27 resolves the exact unit-K symptom from Issue #608.  Its
public `tp_flash2` result retains a distinct inactive-phase composition and
provides active-phase metadata through `numphases(result, true)` and
`is_active_phase(result, i)`.  The Dynamic Distillation adapter now exposes
that retained composition through a diagnostic-only K-value API while keeping
the existing runtime TP-flash methods strict.

One-active-phase results remain classified as one active phase.  A K-vector
formed from a retained inactive composition is labeled
`clapeyron-inactive-flash-estimate`, has `k_is_equilibrium=false`, and is not
used implicitly by runtime equilibrium, energy, density, or hydraulic paths.

## Environment

- Windows
- Julia `1.12.7`
- Clapeyron `0.6.27`
- Python adapter: `pyclapeyron` backed by
  `C:\Users\Thomas Zvolensky\anaconda3\julia_env`

The separate isolated environment at
`C:\Users\Thomas Zvolensky\Documents\ClapeyronBubblePointTest` also resolves
to Julia `1.12.7` and Clapeyron `0.6.27`.

## Issue #608 Fixed State

At the published state

```text
p = 1.6005646620614817e6 Pa
T = 329.8433241022147 K
z = [0.5387358764517459, 0.41587305276545855, 0.04539107078279546]
```

Clapeyron reports one active slot and one zero-fraction retained inactive
slot.  The adapter preserves `phase_count=1`, reports `phase_slot_count=2`,
and obtains:

```text
K = [1.381777574115596, 0.5867762314134225, 0.25472906234541254]
```

The strict runtime method still raises the explicit unavailable-equilibrium-K
error for this one-active-phase TP state.

## Original 54-Call Campaign

The original focused inputs were recovered from:

- workbook: `logs/c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`;
- profile: `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_unitKquarantine_1800s_20260709/column_profile_20260709_194209.csv`;
- 18 selected stage/time states;
- liquid `x`, vapor `y`, and overall `z` bases, giving 54 calls.

Results under 0.6.27:

| Metric | Result |
|---|---:|
| Calls completed | 54 / 54 |
| Errors | 0 |
| Unit-K results | 0 |
| One-active-phase retained estimates | 44 |
| True two-active-phase equilibrium K | 10 |
| Scalar versus batch-style max K difference | 0.0 |

The 0.6.26 campaign produced 40 unit-K calls.  Therefore 0.6.27 corrects all
previously observed unit-K cases in this frozen campaign.  Four additional
one-active-phase states now expose non-unit retained estimates.

Evidence:

- `logs/clapeyron_0627_inactiveK_probe_basis_all_focus_20260828.json`;
- `logs/clapeyron_0627_inactiveK_probe_basis_all_focus_20260828.md`.

## DWSIM PR Comparison

Across the same 54 inputs, DWSIM PR and Clapeyron both produced zero unit-K
results.  The maximum absolute K difference was `0.0416124`.  The worst
absolute log-ratio was `0.154610`, corresponding to a `14.33%` ratio
difference for trace n-pentane at stage 3, time 1780 s, on the liquid basis.

Separated by Clapeyron classification:

| Classification | Calls | Max absolute K difference | Max absolute log-ratio |
|---|---:|---:|---:|
| Retained inactive estimate | 44 | 0.0416124 | 0.154610 |
| Two-active-phase equilibrium | 10 | 0.0410579 | 0.110201 |

These differences are compatible with the already documented PR parameter
and implementation differences; they do not justify silently replacing DWSIM
runtime K-values.

Evidence:

- `logs/dwsim_vs_clapeyron_0627_inactiveK_probe_focus_20260828.json`;
- `logs/dwsim_vs_clapeyron_0627_inactiveK_probe_focus_20260828.md`.

## Adapter Contract

1. Active phase count comes from Clapeyron's 0.6.27 active-phase API, with the
   previous fraction-tolerance logic retained only as compatibility fallback.
2. Composition-row count is recorded separately as `phase_slot_count`.
3. Duplicate inactive rows are rejected and cannot yield unit K-values.
4. Distinct retained inactive rows may yield diagnostic K estimates.
5. Existing runtime flash methods do not consume the diagnostic estimate.
6. Core V3 governing equations and provider permissions are unchanged.
7. DWSIM remains the runtime energy, density, molecular-weight, and diagnostic
   TP-flash authority pending a separately authorized trajectory study.

Reproduction tool: `tools/probe_clapeyron_unit_k.py` with
`--clapeyron-027-inactive-k-diagnostic`.
