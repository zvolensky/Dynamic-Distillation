# DD-098 Core V3 Short Open-Loop Result

Date: 2026-07-25

## Decision

DD-098 passes every frozen gate in its single execution from contract commit
`5ded9f6`.

Core V3 now has a bounded, nonzero, step-refined open-loop transient. The
result authorizes only one separately frozen longer open-loop contract. It
does not authorize controllers, production scaling, or design acceptance.

## Root Hold

The unchanged-input `2.0 s` trajectory completes both requested `1.0 s`
steps without artificial drift:

```text
maximum component rate             7.612471e-8 lbmol/h
maximum relative inventory drift   1.899663e-12
maximum algebraic drift            1.846140e-11
```

Both endpoints retain rank `38/38`, physical states, discrete conservation,
and provider compliance.

## Feed-Step Response

The sole forcing increases all feed component rates and total feed enthalpy
by `0.1%`, preserving feed composition and specific enthalpy.

```text
expected total accumulation        3.968318889e-3 lbmol

dt=1.0 s
  completed steps                  2 / 2
  total accumulation               3.968318889e-3 lbmol
  accumulation relative error      1.286010e-11
  maximum component rate           3.418114 lbmol/h
  evaluations per step             4, 4
  maximum residual                 4.299045e-13
  maximum condition                35.134229

dt=0.5 s
  completed steps                  4 / 4
  total accumulation               3.968318889e-3 lbmol
  accumulation relative error      1.286010e-11
  maximum component rate           3.671886 lbmol/h
  evaluations per step             5, 5, 5, 5
  maximum residual                 1.714674e-12
  maximum condition                35.192351
```

Total inventory increases at every endpoint. Maximum component and energy
conservation errors remain below `3.29e-13` and `1.25e-12`, respectively.
Every endpoint remains positive, temperature ordered, hydraulically physical,
and negative-duty at the condenser.

## Refinement

At `t=2.0 s`, the two perturbed endpoints agree within:

```text
relative component-inventory difference  2.626335e-6
algebraic-coordinate difference          4.459691e-6
temperature difference                   1.054004e-5 F
total-accumulation relative difference   0.0
```

All are comfortably inside the precommitted limits.

## Provider And Performance

All `325,332` governing DWSIM calls obey provider ownership with no fallback:

- direct imposed-phase fugacity;
- declared phase enthalpy;
- declared liquid density.

Wall-clock time is `139.236 s` for the combined root-hold and two independent
perturbed trajectories. The result is numerically successful but expensive.
The central endpoint Jacobians repeatedly solve nested storage bubble
problems, so the current implementation is a correctness reference rather
than a production-speed integrator.

## Interpretation

DD-098 establishes four things that DD-097 could not:

1. accepted endpoints can be chained without repair or projection;
2. a physical input change produces nonzero dynamic motion;
3. global accumulation follows the exact external material balance;
4. halving the step gives a consistent transient endpoint.

The `2 s` duration is too short to establish damping, attraction, long-run
boundedness, or realistic separation response. It also does not address the
DD-094 reduced-root design-point mismatch.

## Next Authorized Increment

DD-099 may draft and precommit one modest longer open-loop contract. It should
retain the same `+0.1%` feed step, compare fixed `1.0 s` and `0.5 s` grids over
no more than `10 s`, and add trajectory-trend gates for bounded rates,
monotone global accumulation, physical margins, endpoint refinement, and
per-step nonlinear effort.

No controller, initializer, pressure dynamics, vapor holdup, production tray
count, or post-result performance optimization is authorized by DD-098.

Primary evidence:

- `logs/dd098_core_v3_short_open_loop_contract_20260725.json`
- `logs/dd098_core_v3_short_open_loop_20260725.json`
- `src/dynamic_distillation/core_v3/short_trajectory_v1.py`
- `tools/run_core_v3_short_open_loop.py`
- `tests/test_core_v3_short_trajectory_v1.py`
