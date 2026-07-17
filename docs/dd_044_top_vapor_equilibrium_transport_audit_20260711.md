# DD-044 Top Vapor Equilibrium and Transport Audit

Date: 2026-07-11

## Scope

This audit examines why increased reflux failed to improve distillate C4 in:

`logs/c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711`

The run used DWSIM PR, active pressure and geometry-based level controllers,
and distillate C4 control through reflux. The dynamic reflux-feasibility cap
was disabled, while a hard reflux limit of 7000 lbmol/h remained. The run was
halted at 600 simulated seconds after moving decisively away from its targets.

Audits were evaluated at 50, 300, and 600 seconds using:

- `tools/audit_vapor_transport_equilibrium_conflict.py`
- `tools/audit_vapor_rhs_material_terms.py`
- `tools/audit_k_state_drift.py`
- `tools/audit_overhead_feasibility.py`

## Finding 1: The higher reflux was not inventory-sustainable

At 600 seconds, the top boundary rates were:

| Quantity | Value (lbmol/h) |
|---|---:|
| Condensate generated | 6431.37 |
| Reflux withdrawal | 7000.00 |
| Distillate withdrawal | 1212.48 |
| Total liquid withdrawal | 8212.48 |
| Net drum inventory rate | -1781.12 |

The reflux alone exceeded condensate generation by 568.63 lbmol/h. Reflux plus
distillate exceeded condensate by 1781.12 lbmol/h, and the geometric drum level
fell from 44.50% at 50 seconds to 36.71% at 600 seconds. This was inventory
drawdown, not a sustainable higher-reflux operating point.

The product-flow field is `top_L_distillate_out_lbmolph`. The similarly named
`Distillate_L_lbmol` field is a liquid inventory and must not be interpreted as
a product rate.

## Finding 2: Pressure was not controlled during the reflux experiment

Top pressure fell from 221.53 psia at 50 seconds to 203.31 psia at 600 seconds,
against a 222.62 psia setpoint. Condenser duty moved from approximately -45.94
to -43.83 MMBtu/h, but the pressure loop did not arrest the decline. Therefore,
the test did not isolate reflux as the only changed operating variable.

## Finding 3: The first active tray's vapor moved away from equilibrium

The strongest product-quality mechanism was the C4 vapor state immediately
below the top boundary:

| Time (s) | Actual vapor C4 | DWSIM target C4 | Pre-equilibrium C4 RHS (lbmol/s) | Applied equilibrium transfer (lbmol/s) | Final C4 RHS (lbmol/s) |
|---:|---:|---:|---:|---:|---:|
| 50 | 0.295250 | 0.194112 | 0.378041 | -0.367196 | 0.010845 |
| 300 | 0.337519 | 0.193571 | 0.264663 | -0.249264 | 0.015399 |
| 600 | 0.397501 | 0.206053 | 0.129933 | -0.106558 | 0.023374 |

The equilibrium term opposed the transport-driven increase, but it never fully
cancelled it. The final C4 vapor-inventory derivative remained positive and
grew, so increasingly C4-rich vapor continued toward the condenser.

## Finding 4: The transport-based limiter suppressed nearly all requested correction

The uncapped equilibrium correction grew as the vapor state moved farther from
the DWSIM target, but the row-wise transport limiter allowed progressively less
of it:

| Time (s) | Estimated raw C4 correction (lbmol/s) | Applied correction (lbmol/s) | Guard scale | Guard limit (lbmol/s) |
|---:|---:|---:|---:|---:|
| 50 | -9.886 | -0.367 | 0.037142 | 0.428403 |
| 300 | -15.198 | -0.249 | 0.016401 | 0.292128 |
| 600 | -22.788 | -0.107 | 0.004676 | 0.129933 |

At 600 seconds, only about 0.47% of the requested row correction survived the
guard. The limiter allowance is based on the instantaneous pre-equilibrium
transport RHS. As that RHS declined, the allowance shrank even though the
accumulated vapor-composition error grew. The limiter can nearly cancel current
transport, but with the accepted multiplier of 1.0 it cannot provide enough
additional correction to remove an existing equilibrium error.

This is the direct mechanism behind the counterintuitive reflux response.
Higher reflux changed transport, but the explicit vapor state was not allowed
to return to the DWSIM equilibrium target. The condenser therefore received
progressively heavier vapor.

## Finding 5: Rate-only diagnostics understate the defect

The maximum relative vapor RHS remained near 0.001/s, while the level
consistency defect worsened:

- Maximum `|K_state - K_thermo|`: 0.922 at 50 s to 1.169 at 600 s.
- Worst final `K_state/K_thermo`: 5.061 for C5 in the upper interior.
- First-active-tray C4 `K_state/K_eq`: 1.318 at 50 s to 2.038 at 600 s.

Large transport-in and transport-out terms cancel numerically, producing a
small final rate while the vapor state remains physically inconsistent. This
confirms that the rate-based dynamic score cannot certify equilibrium quality
by itself.

## Conclusion

The failed reflux experiment combines two problems:

1. A boundary control problem: reflux plus distillate exceeded condensate,
   draining the reflux drum while pressure fell far below setpoint.
2. A model coupling problem: the transport-based equilibrium-transfer limiter
   suppressed the correction needed to bring the explicit vapor state back to
   the DWSIM equilibrium target.

The second problem explains why increased reflux did not improve distillate
quality. This is not evidence that reflux has the wrong physical effect; it is
evidence that the explicit vapor/equilibrium formulation did not preserve the
physical response during the transient.

## Recommended next probe

Do not continue controller tuning yet. Run a short, controlled-pressure probe
from the same checkpoint with sustainable top withdrawals and instrument both
raw and limited equilibrium transfer. Compare the accepted multiplier 1.0
against a narrowly selected alternative treatment that can remove accumulated
equilibrium error without explicitly overshooting transport. Acceptance should
require:

- bounded pressure near its setpoint,
- nonnegative sustainable top-boundary inventory balance,
- vapor composition remaining close to `y_eq`,
- no growth in `K_state/K_thermo`, and
- a non-increasing distillate C4 response to increased sustainable reflux.

## Implemented candidate correction

The model now provides the opt-in mode:

`--equilibrium-relaxation-mode composition-exponential`

For each explicit step, this mode first predicts the vapor component inventory
after material transport. It then moves that predicted state toward the DWSIM
equilibrium composition by the exact bounded fraction `1-exp(-dt/tau)`. In
composition mode, the equilibrium target uses the transport-predicted total
vapor holdup, so the split changes composition without inventing net vapor.
Liquid and vapor component transfers remain equal and opposite, and an
availability guard scales the row if a requested transfer would make either
phase component negative.

This candidate bypasses the instantaneous transport-cancellation limiter that
caused the DD-044 ratchet. The legacy `composition-only` mode remains available
until dynamic validation establishes whether the exponential treatment should
become the hydraulic default.

## Initial validation result

Focused equation and runner tests passed (`154` runner/module checks and `112`
RHS/equilibrium checks). A live DWSIM PR A/B comparison from the same checkpoint
gave the following result at 10 seconds:

| Metric | Legacy transport-limited | Exponential split |
|---|---:|---:|
| First-active-tray vapor C4 | 0.29145 | 0.17744 |
| First-active-tray DWSIM target C4 | 0.19703 | 0.17484 |
| Maximum `|K_state-K_thermo|` | 0.87352 | 0.80405 |
| Dynamic rate score | 1.61 | 4.33 |

The exponential mode produced a larger initial rate because it actively removed
the accumulated disequilibrium that the legacy guard left in place. It did not
produce the former vapor wave. In a 60-second extension, the score decreased
monotonically to `2.006`, distillate C4 decreased to `0.19178`, top pressure was
`221.315 psia`, and first-active-tray vapor C4 was `0.12205` against a DWSIM
target of `0.12022`. Global mass closure was approximately
`4.5e-12 lbmol/h`, and the component-availability guard remained inactive.

The candidate therefore fixes the confirmed transport-limiter ratchet and is
safe enough for a longer validation probe. It is not yet the hydraulic default:
the 60-second rate gate still failed, top inventory and pressure were still
moving, and final maximum `|K_state-K_thermo|` remained `0.80986`.

## Extended 300-second result

The 10-second exponential checkpoint was continued for another 290 seconds
with the reflux feasibility cap restored. The top geometry-level controller was
retuned from `Kc=1, Ti=600 s` to `Kc=5, Ti=300 s` so distillate draw could move
toward the available condensate budget without an abrupt restart command reset.

The run remained bounded and did not reproduce the vapor wave. Final results
were:

| Metric | Final value |
|---|---:|
| Top pressure | 221.436 psia |
| Distillate C4 | 0.156249 |
| Top geometric level | 44.23% |
| Condensate | 7605.17 lbmol/h |
| Reflux | 5967.32 lbmol/h |
| Distillate | 458.15 lbmol/h |
| Top inventory rate | +1179.69 lbmol/h |
| Overhead vapor / bottom vapor | 0.9471 |
| Dynamic score | 1.5446 (fail) |

The top boundary transitioned from depletion to recovery after approximately
180 continuation seconds. The faster level loop then reduced distillate too far
while rebuilding the underfilled drum, so this run is not an operating-point
acceptance case. It does show that the previous low-overhead collapse is not
intrinsic to the exponential equilibrium treatment.

At 290 continuation seconds, the vapor transport/equilibrium audit found target
composition discrepancies generally near `1e-4`, and the first-active-tray
vapor remained close to its logged thermodynamic target. No vapor-flow clamp was
active. Maximum `|K_state-K_thermo|` remained `0.8604`, however. The worst K
record moved into the lower interior and reflects a remaining mismatch between
the current liquid composition and the flash phase composition even while vapor
tracks `y_target`. The exponential vapor correction therefore resolves DD-044's
transport-limiter ratchet but does not, by itself, place both integrated phases
on the complete thermodynamic flash manifold.

Extended run artifacts:

`logs/c3c4_dd044_exponential_eq_continue290s_topKc5_20260711`
