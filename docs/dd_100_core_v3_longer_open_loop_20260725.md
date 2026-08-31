# DD-100 Core V3 Longer Open-Loop Result

Status: Historical reference. This result pertains to the earlier fixed-pressure reduced DAE path and is superseded by the accepted vapor-holdup C3/C4 dynamic model described in `docs/dynamic_model_current_state_2026-08-20.md`.

## Decision

DD-100 passes every frozen gate in its single execution from contract commit
`d92d354`.

The corrected Core V3 implicit formulation now has bounded evidence for
repeated nonzero open-loop stepping over `10 s`, including independent time-grid
refinement. This authorizes the next explicit dynamic-scope decision only. It
does not establish production-horizon, controller, pressure-dynamic, or vapor-
holdup acceptance.

## Campaign

All trajectories began independently from the accepted DD-094 root:

- stationary root hold: 5 steps at `dt=1.0 s`;
- `+0.1%` feed-throughput step: 10 steps at `dt=1.0 s`;
- independent `+0.1%` feed-throughput step: 20 steps at `dt=0.5 s`.

All 35 requested endpoints completed without retry or substepping.

## Numerical result

- Maximum scaled residual: `1.6155e-12`.
- Every endpoint rank: `38/38`.
- Worst Jacobian condition: `7.3877e5`, below the `1e8` gate.
- Maximum nonlinear evaluations in one endpoint: `6`.
- Maximum transient component rate: `3.6719 lbmol/h`.
- Root-hold maximum component rate: `7.8990e-8 lbmol/h`.
- Root relative inventory drift: `4.1751e-12`.

Every endpoint remains finite, positive, temperature ordered, hydraulically
below tray spacing, physically signed at the condenser, and within the frozen
component/energy conservation and equilibrium limits.

## External balance and refinement

The exact expected total accumulation over `10 s` is
`0.0198415944444 lbmol`.

| Grid | Actual accumulation (lbmol) | Relative error |
|---|---:|---:|
| `dt=1.0 s` | `0.0198415944442` | about `1.29e-11` |
| `dt=0.5 s` | `0.0198415944446` | about `1.01e-11` |

The refined endpoints differ by:

- relative inventory: `4.3054e-6`;
- algebraic coordinates: `6.8089e-6`;
- temperature: `1.6004e-5 F`;
- relative accumulated inventory: `2.2919e-11`.

All refinement gates pass comfortably.

## Efficiency

The campaign completes in `69.264 s` and records `130,368` provider calls, or
`3,724.8` calls per endpoint. This passes the frozen limits of `180 s` and
`6,000` calls per endpoint.

No call uses nested bubble reconstruction. All governing calls retain the
declared DWSIM fugacity, phase-enthalpy, and liquid-density ownership with no
fallback.

## Interpretation

DD-100 demonstrates that DD-099's speedup survives repeated, moving implicit
steps. It also shows that the fixed-pressure reduced DAE remains conservative,
physical, and time-grid consistent over the bounded `10 s` disturbance window.

The next work must choose and freeze one scope increase. It should not combine
several missing layers at once. Candidates include a materially longer
fixed-pressure open-loop horizon or one separately derived physical layer such
as pressure dynamics. Controllers remain premature until their manipulated and
controlled variables exist in an accepted dynamic architecture.
