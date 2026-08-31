# DD-278 Core V3 Drum-Level Controller Tuning

## Decision

Increasing the reflux-drum level-controller proportional gain from `0.5` to
`2.0`, then to `4.0`, while retaining `Ti=120 s`, progressively damps the long
terminal inventory cycle. The change does not disturb the column equations,
thermodynamics, pressure dynamics, sump controller, fixed duties, or reflux
specification.

Retain `Kc=4.0, Ti=120 s` as the current Core V3 reflux-drum level tuning. Its
30-minute assessment reduced the comparable opposite score lobe from `5.909`
with `Kc=2.0` to about `4.242`, a further `28.2%` reduction. The score then
returned below `1.0` by `1620 s` and ended at `0.492`. The endpoint passed the
steady-state, physicality, rank, conservation, and controller-memory gates.

This establishes useful damping, not proof that all future cycles vanish.
Further gain changes are not justified before a normal operating continuation
shows whether the next lobe is smaller again.

## Bumpless Handoff

The production Core V3 runner now accepts:

- `--drum-level-kc`;
- `--drum-level-ti-sec`.

When tuning differs from the source checkpoint, the runner reconstructs live
terminal levels from saved inventories, temperatures, pressures, DWSIM liquid
densities, and workbook geometry. It then recalculates PI memory so the saved
product outputs are unchanged at the handoff. Effective tuning is stored in
all final and recovery checkpoints and inherited automatically by later
continuations.

The one-step serial handoff retained distillate flow within `0.11 lbmol/h` of
the source value over `0.25 s`; residual was `2.61e-12`, rank was `262/262`,
and every physical gate passed. An earlier parallel preflight stopped only at
the existing all-workers-participated accounting guard before accepting an
endpoint; it did not expose a physical or tuning failure.

## Five-Minute Screen

The score increased from `8.75` to a crest of `9.291` at about `180 s`, then
declined to `9.100` at `300 s`. Drum level returned to `49.991%`. Final
residual was `5.32e-13`, rank was `262/262`, and the endpoint was physical.

## Thirty-Minute Assessment

The score fell through the gate at `780 s`, reached `0.146` at `840 s`, then
formed the opposite lobe. That lobe reached `5.909` near `1770 s` and was
slightly lower at the final `1800 s` point.

Final conditions were:

| Quantity | Value |
|---|---:|
| Steady-state score | `5.9057` |
| Distillate flow | `2078.6987 lbmol/h` |
| Bottoms flow | `4642.8267 lbmol/h` |
| Drum level | `49.7726%` |
| Sump level | `49.9992%` |
| Drum pressure | `221.2588 psia` |
| Scaled nonlinear residual | `8.37e-13` |
| Jacobian rank | `262/262` |

The drum level ranged from `47.8784%` to `49.9901%` during this segment. The
sump remained essentially at setpoint. Pressure remained smooth and ordered.

## Kc 4.0 Assessment

The five-minute screen remained physical and reduced the score from `5.906` to
`4.563`. The following 30-minute continuation first passed below `1.0`, formed
an opposite lobe of about `4.242` near `1020 s`, and returned below `1.0` at
`1620 s`. It reached `0.057` at `1740 s` and ended at `0.492` as the next small
turn began.

Final conditions were:

| Quantity | Value |
|---|---:|
| Steady-state score | `0.4918` |
| Distillate flow | `2470.8679 lbmol/h` |
| Bottoms flow | `4629.5833 lbmol/h` |
| Drum level | `49.3474%` |
| Sump level | `50.0066%` |
| Drum pressure | `221.0894 psia` |
| Condenser duty | `-50.8948 MMBtu/h` |
| Reboiler duty | `54.7060 MMBtu/h` |
| Scaled nonlinear residual | `1.66e-12` |
| Jacobian rank | `262/262` |
| Jacobian condition | `1.28e7` |

During the 30-minute segment, drum level remained between `49.3355%` and
`51.0511%`; sump level remained between `49.9899%` and `50.0072%`. Pressure
remained ordered and smooth. The run completed `1800 s` in `9456.9 s` wall
time, a simulation/wall ratio of `0.1903`.

## Next Step

Keep `Kc=4.0, Ti=120 s` for the next ordinary continuation. Do not perform
another controller-gain sweep now. Confirm that the next score lobe is smaller
than `4.242`, terminal levels remain bounded, and the score repeatedly returns
below `1.0`. Reopen tuning only if the lobe stops shrinking or a controller
output approaches a bound.

Evidence:

- `logs/core_v3_parallel_level_settle_followup1800s_20260829`;
- `logs/core_v3_drum_kc2_bumpless_smoke_serial_20260829`;
- `logs/core_v3_drum_kc2_screen300s_20260829`;
- `logs/core_v3_drum_kc2_assessment1800s_20260829`;
- `logs/core_v3_drum_kc4_screen300s_20260829`;
- `logs/core_v3_drum_kc4_assessment1800s_20260829`;
- `tools/run_core_v3_dynamic.py`;
- `tests/test_run_core_v3_dynamic.py`.
