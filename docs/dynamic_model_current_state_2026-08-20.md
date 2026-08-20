# Dynamic Model Current State

Date: 2026-08-20

Status: Authoritative current-state summary. This supersedes
`docs/dynamic_model_current_state_2026-07-12.md` for current decisions while
retaining that document as historical evidence.

## Executive conclusion

Core V3 has crossed an important boundary. The repository now contains a
complete 20-volume C3/C4 model with explicit liquid and vapor component
inventories, total two-phase energy storage, fugacity equilibrium, vapor EOS
closure, Francis liquid hydraulics, vapor pressure-drop equations, and live
terminal level control. It has an accepted stationary root and has completed
short implicit dynamic trajectories without clipping, profile forcing,
relaxation, property fallback, or a fixed-pressure anchor.

DD-274 is the latest accepted result. It releases reflux-drum pressure, fixes
condenser duty, retains both geometry-based level controllers, and advances the
model for 30 seconds. All 120 nominal endpoints and the final half-step
refinement pass. Pressure responds smoothly and remains positive and ordered.

This is strong evidence that the present equations are internally coherent for
short dynamic operation. It is not yet evidence of long-term convergence,
closed-loop pressure control, disturbance robustness, or external physical
validation.

## Modeled column

The current C3/C4 topology has 20 physical control volumes:

- one reflux drum receiving the total-condenser liquid;
- 18 interior equilibrium-stage volumes, including the feed-stage role;
- one combined reboiler and bottoms-sump volume.

Every physical volume owns conserved liquid and vapor component inventories
and total two-phase energy. Vapor composition comes only from vapor inventory.
Pressure follows from vapor inventory, temperature, vapor free volume, EOS
closure, and interstage pressure loss. Liquid flow is owned by Francis
hydraulics. Vapor flow is coupled through energy and pressure-drop equations.

Product composition is always the live composition of its well-mixed terminal
liquid inventory. Drum level manipulates distillate flow; sump level manipulates
bottoms flow.

## Accepted stationary foundation

DD-245 established the full 20-volume stationary root:

| Quantity | Accepted value |
|---|---:|
| Scaled residual | `3.05e-11` |
| Numerical rank | `260 / 260` |
| Jacobian condition | `5.24e4` |
| Pressure range | `220.44` to `221.556 psia` |
| Distillate | `2519.764 lbmol/h` |
| Bottoms | `4623.210 lbmol/h` |
| Condenser duty | `-50.9973 MMBTU/h` |
| Total liquid inventory | `2907.909 lbmol` |
| Total vapor inventory | `463.640 lbmol` |

Material, energy, equilibrium, EOS, terminal, physical-domain, and provider
ownership gates all pass. DD-246 through DD-248 then proved an exact dynamic
handoff and a motionless first implicit hold step.

## Accepted dynamic evidence

The accepted sequence is:

- DD-249: one moving step and timestep refinement pass after a `0.1%` feed and
  feed-enthalpy increase.
- DD-259 and DD-262: five-second and adjudicated 30-second open-loop
  vapor-holdup trajectories pass conservation, physicality, rank, refinement,
  and provider gates.
- DD-263 and DD-264: workbook-backed drum/sump geometry and bumpless PI level
  control pass structurally and numerically.
- DD-266 and DD-268: the first controlled endpoint and one-second controlled
  path are scientifically accepted after correcting assessment formulas that
  did not account for moving controller boundaries.
- DD-269: the five-second controlled trajectory passes.
- DD-270: the first 30-second attempt stops cleanly at an artificial cumulative
  product-coordinate bound, not a model instability.
- DD-271: corrected generic product bounds permit the complete 30-second
  level-controlled trajectory to pass under a fixed pressure anchor.
- DD-272 and DD-273: the pressure anchor is replaced one-for-one by a fixed
  condenser-duty equation, preserving a full-rank `262 x 262` system and a
  stable live Jacobian.
- DD-274: the first 30-second dynamic-pressure trajectory passes every frozen
  gate.

## Latest accepted endpoint

DD-274 continues from the accepted DD-271 endpoint with condenser duty fixed at
`-50.894826 MMBTU/h`, both level controllers active, and no pressure controller.

| Quantity | Start | End at 30 s | Change |
|---|---:|---:|---:|
| Reflux-drum pressure, psia | 220.440000 | 220.433121 | -0.006879 |
| Top-tray pressure, psia | 220.487576 | 220.480659 | -0.006917 |
| Bottom pressure, psia | 221.553508 | 221.545605 | -0.007903 |
| Distillate, lbmol/h | 2501.183 | 2482.756 | -18.427 |
| Bottoms, lbmol/h | 4820.038 | 4974.937 | +154.899 |
| Drum level, fraction | 0.440781 | 0.440795 | +0.000014 |
| Sump level, fraction | 0.522747 | 0.521192 | -0.001555 |

The final top-tray-to-drum pressure drop is `0.047538 psia`. Maximum pressure
movement in any `0.25 s` step is `0.0001124 psia`; the final full-step versus
two-half-step pressure difference is `1.76e-7 psia`. Final scaled residual is
`1.14e-12`; numerical rank is `262 / 262`; condition is `1.07e7`. Component
identity error is `6.16e-11 lbmol` and energy identity error is
`4.28e-6 BTU`.

## Pressure ownership

The reflux drum is no longer a pressure boundary. DD-272 removes
`P[reflux_drum] - P_anchor = 0` and inserts
`Q_C - Q_C_specified = 0` in the same row slot. Condenser duty remains in the
top total-energy balance. Absolute pressure is therefore determined by the
conserved vapor inventory, energy/temperature state, free vapor volume, EOS,
and the linked pressure-drop equations.

The top tray and reflux drum are coupled by their vapor link. The pressure-drop
equation requires top-tray pressure to equal drum pressure plus liquid-head and
dry-tray losses. DD-274 demonstrates that the whole pressure profile moves
together while retaining that local loss.

## Active controls and specifications

Active in DD-274:

- reflux-drum level PI controller manipulating distillate flow;
- bottoms-sump level PI controller manipulating bottoms flow;
- geometry-based level calculations from workbook vessel dimensions.

Specified in DD-274:

- condenser duty at `-50.894826 MMBTU/h`;
- reflux flow, reboiler duty, feed conditions, and controller tuning inherited
  unchanged from the accepted handoff.

Not active:

- pressure controller;
- composition controller;
- profile forcing, flow caps, phase relaxation, clipping, or thermo fallback.

## Thermodynamic provider

DWSIM Peng-Robinson is the accepted runtime provider for this hydrocarbon case.
Provider ownership and no-fallback gates pass throughout the accepted Core V3
sequence.

Clapeyron remains outside the accepted runtime path pending release and focused
verification of its active-phase and single-phase/incipient-phase API. That
future work should require an adapter change, not a change to the Core V3
governing equations. Discarded or incipient K-values remain diagnostic unless a
separate runtime contract authorizes them.

## What is now established

- A physical full-rank stationary root exists for the complete 20-volume
  vapor-holdup formulation.
- The stationary root maps cleanly into the implicit dynamic state.
- The model can move conservatively under a small input change.
- Explicit vapor holdup and total two-phase energy can be advanced repeatedly.
- Geometry-based terminal level controllers act smoothly and in the expected
  directions.
- Reflux-drum pressure can be released and allowed to respond dynamically under
  fixed condenser duty.
- Pressure remains positive, ordered, smooth, and timestep-consistent over the
  accepted 30-second pressure-dynamic window.
- DWSIM provider ownership, equilibrium, EOS, material, and energy checks remain
  intact.

## What remains open

- DD-274 covers only 30 seconds of free-pressure behavior. Long-duration drift,
  settling, and controller interaction are not yet established.
- No pressure controller has been designed or tested on the Core V3
  pressure-dynamic model.
- A pressure or composition disturbance has not yet been applied after release
  of the pressure anchor.
- Production operating specifications and final separation performance have not
  yet been accepted against independent or plant evidence.
- Runtime remains expensive: DD-274 required 658,920 logical provider calls and
  220.1 seconds of continuation wall time for 30 simulated seconds.
- The full initialization and restart workflow still needs a production-facing
  serialized artifact and user-level runner integration around the accepted
  stationary and dynamic contracts.

## Retired paths

The following remain historical evidence and shall not be revived as current
architecture:

- raw ChemSep or Excel profiles treated as complete dynamic initial states;
- checkpoint repair and least-movement projection;
- manual staged steady-state continuation;
- the prescribed-vapor Core V2 Gate C operating specification;
- explicit equilibrium relaxation and profile-owned liquid traffic as
  substitutes for physical closure;
- fixed reflux-drum pressure as the final production pressure treatment.

## Next decision

The next defensible experiment is a separately frozen longer fixed-duty hold
from the DD-274 endpoint, retaining both level controllers and no pressure
controller. Its purpose is to determine whether the small downward pressure
trend decays, persists, or accelerates. The contract should include pressure
trend, level-controller authority, composition, conservation, refinement,
provider-call, and wall-time gates. Pressure-control design should follow only
after the open-loop pressure behavior is characterized over a longer window.

## Primary references

- `docs/dd_245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.md`
- `docs/dd_262_core_v3_c3c4_vapor_holdup_thirty_second_balance_20260820.md`
- `docs/dd_263_core_v3_vapor_holdup_terminal_control_contract_20260820.md`
- `docs/dd_269_core_v3_c3c4_vapor_holdup_terminal_control_five_second_20260820.md`
- `docs/dd_271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_20260820.md`
- `docs/dd_272_core_v3_vapor_holdup_dynamic_pressure_contract_20260820.md`
- `docs/dd_273_core_v3_vapor_holdup_dynamic_pressure_residual_20260820.md`
- `docs/dd_274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_20260820.md`
- `docs/core_v3_vapor_holdup_implementation_plan_20260819.md`
- `docs/model_architecture.md`
- `docs/requirements.md`
- `docs/issue_log.md`
