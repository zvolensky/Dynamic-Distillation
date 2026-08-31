# DD-277 Core V3 Level-Controller Settling Study

## Decision

The dynamic column equations and implicit endpoint solver remain healthy over
the one-hour level-controller settling sequence. The observed long wave is a
terminal inventory-control transient, not a pressure, thermo, conservation,
or nonlinear-solver failure.

The run does not establish a durable steady state. It passes the complete
steady-state gate for four minutes, then leaves the gate as the drum-level PI
loop overshoots. A single score crossing is therefore insufficient for
acceptance. Future accepted initialization should place terminal inventories
at their declared level setpoints and initialize PI memory bumplessly at the
stationary product rates. Controller tuning may then be studied separately;
the governing column equations should not be changed on this evidence.

## Trajectory

The bounded campaign continued the accepted dynamic-pressure checkpoint with:

- live DWSIM Peng-Robinson thermodynamics;
- `0.25 s` backward-Euler timesteps;
- eight persistent parallel Jacobian workers;
- fixed condenser duty of `-50.894826 MMBTU/h`;
- fixed reboiler duty of `54.706000 MMBTU/h`;
- prescribed reflux of `5952.48 lbmol/h`;
- active geometry-based distillate-drum and sump level controllers;
- no pressure controller.

The first 30-minute segment reached a score peak of `8.6217` at `1290 s`,
after which the inventory wave reversed. The following 15-minute segment
reduced the score from `8.0382` to `4.2994`; drum pressure crested at
`222.673482 psia` at `780 s` within that segment and then declined.

The final 15-minute segment produced this acceptance history:

| Segment time | Steady-state score | Gate flag |
|---:|---:|---:|
| `480 s` | `1.0791` | fail |
| `510 s` | `0.8593` | pass |
| `600 s` | `0.1918` | pass |
| `630 s` | `0.0330` | pass |
| `750 s` | `0.9399` | pass |
| `780 s` | `1.1678` | fail |
| `900 s` | `2.0786` | fail |

The score is controlled by whole-column accumulation. Its near-zero value at
`630 s` marks the instant when total product flow nearly equals feed flow; it
does not mean all controller and inventory motion has settled.

## Final Endpoint

| Quantity | Final value |
|---|---:|
| Distillate flow | `2683.1273 lbmol/h` |
| Bottoms flow | `4616.3597 lbmol/h` |
| Drum level | `55.0813%` |
| Sump level | `49.9954%` |
| Drum pressure | `222.254905 psia` |
| Distillate temperature | recorded in the summary CSV |
| Scaled nonlinear residual | `1.7803e-12` |
| Jacobian rank | `262/262` |
| Jacobian condition | `1.5450e7` |
| Physical endpoint gate | pass |
| Final steady-state score | `2.0786` |
| Final steady-state flag | fail |

The final distillate flow is above the instantaneous inventory-neutral value,
so total inventory is decreasing. The sump loop is effectively settled at its
setpoint. The drum loop remains above setpoint and is completing a much slower
cycle.

## Interpretation

The study establishes four useful facts:

1. Core V3 can execute long, physical, fully ranked dynamic trajectories.
2. Dynamic drum pressure remains bounded and responds smoothly through the
   inventory transient.
3. Geometry-based level-control signs and ownership are correct.
4. Starting a level-controlled run from terminal inventories away from their
   setpoints creates a long PI settling wave that can temporarily pass a
   pointwise steady-state gate.

The next initializer task is therefore to solve or construct a controller-ready
stationary handoff with terminal levels at their setpoints, stationary `D/B`,
and consistent PI memory. A controller-tuning experiment is secondary and
must not be used to hide an inconsistent initial terminal inventory.

## Recovery Improvement

The first 15-minute attempt stopped after `840 s` and had no restart artifact
because the production runner previously wrote a checkpoint only after normal
completion. The runner now atomically refreshes
`core_v3_recovery_checkpoint_<run_id>.npz` at every CSV logging point. A live
one-step smoke test proved that the recovery and normal checkpoints contain
identical numerical arrays and the correct elapsed simulation time.

Evidence:

- `logs/core_v3_parallel_level_settle_1800s_20260828`;
- `logs/core_v3_parallel_level_settle_continue900s_retry_20260828`;
- `logs/core_v3_parallel_level_settle_final900s_20260828`;
- `logs/core_v3_recovery_checkpoint_smoke_20260828`;
- `tools/run_core_v3_dynamic.py`.
