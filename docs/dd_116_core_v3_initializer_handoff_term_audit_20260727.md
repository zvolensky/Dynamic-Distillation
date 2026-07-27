# DD-116 Core V3 Initializer Handoff Term Audit Result

## Formal Decision

- Classification: `handoff_discontinuity_not_resolved`
- Decision: `stop_core_v3_initializer_work`
- Contract commit: `f5117ed`
- Wall clock: `0.162 s`
- Provider calls: `85`
- Solve, Jacobian, timestep, controller, initializer, or trajectory: `False`

DD-116 formally fails because the precommitted `physical_reproduction` gate
also included reproduction of DD-115's nominal component-rate coordinates.
No DD-116 rerun or gate change is permitted.

## Substantive Finding

The balance evidence does not show an equation or ownership discontinuity.
All three saved states reproduce pressure, temperature, liquid flow, vapor
flow, product flow, and condenser duty exactly. Every material and energy term
keeps the same owner. Signed term sums reproduce the saved component rates
within `7.18e-14` scaled and the saved energy rates within `2.74e-13` scaled.

The largest initial component-rate change is bottom-volume n-butane:

| Bottom n-butane term, `t=0` to `0.5 s` | Change, lbmol/h |
|---|---:|
| Vapor out to stripping | `-307.6996` |
| Liquid in from stripping | `+5.8515` |
| Liquid out as bottoms | `+0.5544` |
| **Net rate change** | **`-301.2936`** |

The corresponding bottom energy-rate change is almost entirely the same vapor
traffic:

| Bottom energy term, `t=0` to `0.5 s` | Change, BTU/h |
|---|---:|
| Vapor out to stripping | `-955,654.9` |
| Liquid in from stripping | `-2,980.2` |
| Liquid out as bottoms | `+2,299.3` |
| Reboiler duty | `0.0` |
| **Net rate change** | **`-956,335.8`** |

The largest vapor-flow movement is
`V[combined_reboiler_sump->stripping_tray]`, which rises by
`437.6386 lbmol/h`. DD-115's first transient is therefore a balance-explained
response of the energy-owned bottom vapor link, not an unexplained source,
sink, or ownership switch.

## Why The Formal Gate Failed

DD-115 uses a positive exponential inventory update. Its nonlinear unknown is
a nominal logarithmic rate coordinate, while its evaluated physical component
rate is the exact finite-step inventory difference. The step outcome stores:

- `final_coordinates`: the nominal solver coordinate;
- `component_rate_lbmolph`: the effective finite-step physical rate.

DD-116 correctly reconciles the physical rate from the balance terms, but its
fresh direct DAE evaluation interprets `final_coordinates` as an ordinary
continuous rate coordinate. That creates differences of `3.079e-5` at
`0.5 s` and `2.910e-5` at `1.0 s` on the declared scale. The zero-time state,
which has no finite-step coordinate transformation, reproduces exactly.

This is a representation mismatch in saved DD-115 evidence, not failed
pressure, temperature, flow, duty, material-balance, or energy-balance
reproduction. It was nevertheless included in the frozen aggregate gate, so
the raw DD-116 failure remains binding.

## Initializer Objective

DD-112 minimized rather than constrained the conserved rates:

| Objective block | Contribution |
|---|---:|
| Conserved-state movement | `0.174636` |
| Conserved rates | `0.035004` |
| Algebraic movement | `2.080589` |
| **Total** | **`2.290229`** |

The largest normalized rate coordinate is `0.063002`. Thus the initializer
preferred smaller rates with weight `10`, but it never established that a
zero-rate state was feasible under the retained totals, terminal holdups, and
operating specifications.

## Next Decision

The frozen result does not authorize further Core V3 initializer work. A
static, zero-property-call adjudication could separately determine whether the
failed aggregate gate was non-applicable because all actual physical fields
and balance rates reproduced. Such an adjudication requires explicit
authorization and must not alter or rerun DD-116. If accepted, the only next
technical work should be a property-free structural feasibility audit asking
whether exact zero rates can coexist with the retained physical constraints.

## Evidence

- Frozen contract: `docs/dd_116_core_v3_initializer_handoff_term_audit_contract_20260727.md`
- Contract data: `logs/dd116_core_v3_initializer_handoff_term_audit_contract_20260727.json`
- Result data: `logs/dd116_core_v3_initializer_handoff_term_audit_20260727.json`
- Diagnostic ledger: `src/dynamic_distillation/core_v3/handoff_balance_audit_v1.py`
- Runner: `tools/audit_core_v3_initializer_handoff_terms.py`
