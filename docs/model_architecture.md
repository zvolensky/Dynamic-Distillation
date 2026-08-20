# Dynamic Distillation Model Architecture

This document describes the current architecture of the dynamic distillation model in this repository.
It is intended as an implementation-level reference for model behavior, coupling, and runtime execution.

For project terminology, see `docs/glossary.md`.

## Design Complexity and Initialization Implications

This model differs fundamentally from simplified textbook treatments of distillation. Rather than employing **Constant Molar Overflow (CMO)** assumptions and implicit hydraulics, the column uses:

- **Explicit vapor volume** with physical rigidity constraints (fixed shell volumes)
- **Rigorous energy topology** with temperature and enthalpy states on trays and boundary vessels
- **Hydraulic-pressure and explicit vapor-inventory paths** that are intended to be coupled

The intended formulation resembles the DAE structure used by rigorous commercial dynamic simulators. The current implementation does not yet complete that structure: DD-060 shows that hydraulic pressure and pressure implied by explicit vapor holdup can disagree materially, and the accepted composition-only equilibrium path preserves phase totals. This is an open model-closure issue, not merely an initialization sensitivity.

In consequence, initialization is not a trivial "switch to dynamics" operation. A future rigorous formulation will require consistent DAE initialization, but model ownership must first be made internally consistent. An initializer cannot drive all derivatives to a meaningful zero while pressure, phase totals, and energy have competing closures.

See `docs/dynamic_column_initialization_strategy.md` for the mathematical foundation and practical workflow.
See `docs/initialization_code_status.md` for the current support status of initialization, reconciliation, and startup-homotopy tooling.
See `docs/dynamic_model_current_state_2026-07-12.md` for the latest C3/C4 model-state summary and external-review framing.

2026-07-18 architecture decision: DD-075 retires the current direct conserved
steady-state formulation as a production initializer path. The external
review confirms that the v1 runtime is best described as a sequential hybrid,
not a completed DAE. V2 will be a separately derived equilibrium-stage DAE
with one owner per quantity. Its first layer deliberately uses prescribed
pressure, negligible vapor holdup, conserved component/internal-energy
states, algebraic equilibrium, Francis-only tray liquid flow, and prescribed
rectifying/stripping vapor rates for the first feasibility layer. See
`docs/dd_076_equilibrium_dae_v2_architecture_contract_20260718.md`.

2026-07-18 first implementation result: DD-077's initial structural registry
stopped at rank `49/51` because fixed product flows left the drum and bottom
liquid amounts unowned. Specifying those terminal amounts and solving `D/B`
produced a `53 x 53`, full-rank registry with exact symbolic conservation and
clean pressure, vapor-flow, and Francis ownership. See
`docs/dd_077_core_v2_structural_registry_20260718.md`.

2026-07-18 source-equation result: DD-078's property-free v2 assembly matches
the accepted independent Skogestad translation within `5.6e-16`, preserves
global material balances to roundoff, and evaluates the tabulated steady
profile at `3.7e-8 /min`, inside the declared `1e-7 /min` gate. The repository's
mini8 assets are reserved for later property/energy and reduced-column gates
as compact data and audit scaffolding, not as independent solution truth. The
next authorized increment is the bounded Gate A dynamic-integration
comparison. See `docs/dd_078_core_v2_source_equation_gate_20260718.md`.

2026-07-18 Gate A completion: DD-079 integrates nominal drift, the accepted
`+1%` feed step, and a bounded perturbed state for `500 min`. V2/reference
trajectory error is at most `3.85e-11` normalized, BDF/Radau agreement is at
most `1.60e-9`, and solver-integrated material closure is below `2.77e-12`.
All states remain physical without clipping or safeguards. Gate B is now
authorized on one representative mini8 inventory volume with prescribed
pressure and live DWSIM properties. See
`docs/dd_079_core_v2_gate_a_dynamics_20260718.md`.

2026-07-18 Gate B completion: DD-080 reconstructs one role-selected mini8
feed volume from conserved component inventory and live DWSIM PR internal
energy at prescribed pressure. Five static states converge from three
predefined guesses with rank `3/3` and Jacobian condition below `3`.
Live-density geometry is physical, and four BDF/Radau local dynamics pass
with worst normalized method disagreement `3.75e-9`, component conservation
`4.60e-16`, and energy conservation `2.01e-16`. Gate C is now authorized as
one five-volume prescribed-pressure Francis column. See
`docs/dd_080_core_v2_gate_b_one_volume_20260718.md`.

2026-07-18 Gate C pre-solve result: DD-081 assembles the five-volume live
DWSIM PR residual without taking a nonlinear step. Direct `NL/x`
reconstruction eliminates 15 identity coordinates from DD-077's structural
ledger, producing a `38 x 38` numerical system because the liquid-only reflux
drum has no equilibrium-vapor outlet. The canonical state and four predefined
perturbations are structurally and numerically rank `38/38` at both Jacobian
steps, with worst condition `1.19e6`, machine-precision component/energy
telescoping, and no unregistered coupling or safeguard. The canonical scaled
residual is still `0.511`, so no steady root has been established. One bounded
DD-082 solve is authorized. See
`docs/dd_081_core_v2_gate_c_five_volume_20260718.md`.

2026-07-18 Gate C stop result: DD-082 executes the precommitted three-start
bounded campaign. All starts converge to the same full-rank endpoint within
`2.12e-9`, but retain the same scaled residual floor of `9.16e-3`.
`N[reflux_drum,n-Pentane]` is active at its upper `50x` reference bound, and
the remaining floor is dominated by reflux-drum and rectifying n-pentane
component balances. Condition improves to about `1.92e4`; conservation and
physicality otherwise pass. Under the frozen hard stop, Gate C fails and this
prescribed-pressure, prescribed-vapor five-volume operating specification is
retired. No wider-bound or alternate-solver DD-083 is authorized. See
`docs/dd_082_core_v2_gate_c_steady_solve_20260718.md`.

2026-07-18 post-Gate-C structural decision: DD-083 does not retune the failed
prescribed-vapor campaign. It replaces the two prescribed section rates with
four independent vapor-link unknowns and closes the steady MESH ledger with
all component fugacity equalities at the four equilibrium outlets. For three
components the resulting system is `37 x 37`, structurally rank `37`, with
exact symbolic component/energy telescoping and no profile, cap, relaxation,
controller, or previous-step flow owner. This is a structural result only.
One frozen live-property numerical audit may be designed next; no nonlinear
solve or dynamic integration is authorized. See
`docs/dd_083_energy_owned_vapor_flow_architecture_20260718.md`.

2026-07-18 energy-owned numerical result: DD-084 evaluates the frozen
`37 x 37` residual with live DWSIM PR at the role-mapped seed and one
deterministic perturbation. Every Jacobian is rank `37/37` at `h` and `h/2`,
with worst condition `1.78e6`, no zero row/column, no off-registry coupling,
and component/energy telescoping near machine precision. The canonical
scaled residual is `0.398`, led by Francis mismatch, so no root is claimed.
One bounded steady-root campaign may be drafted and precommitted next; no
solve or dynamic integration is yet authorized. See
`docs/dd_084_energy_owned_vapor_numerical_audit_20260718.md`.

2026-07-18 energy-owned root result: DD-085 executed once from precommit
`eaa7cc3`. All three starts reach the same interior algebraic root within
`1.56e-12`, with scaled residual at most `2.55e-13`, rank `37/37`, condition
about `751.5`, and roundoff conservation. The root fails only physical
temperature ordering: the reflux drum is `166.131 F`, `3.233 F` hotter than
the rectifying equilibrium stage supplying the inventory-free total
condenser while duty removes heat. Under the frozen hard stop, the
five-volume energy-owned steady architecture is retired. No DD-086 tuning,
dynamic DAE contract, or integration is authorized. See
`docs/dd_085_energy_owned_vapor_steady_root_20260718.md`.

2026-07-18 condenser-boundary successor: DD-086 confirms the DD-085 drum
state is stable vapor, not liquid. At `166.131 F`, `218.44 psia`, and the
reported drum composition, live DWSIM PR gives Rachford-Rice vapor fraction
essentially `1.0`, even though the phase-specific liquid enthalpy closes the
fixed-duty energy target to `4.73e-11 BTU/lbmol`. The successor does not
retune that duty. It promotes `Q_C` to an unknown and adds an incipient-vapor
composition plus full bubble-fugacity equations, yielding a saturated-liquid
total-condenser registry of `40 x 40`, structural rank `40`, and nullity zero.
One frozen live numerical audit may be designed next; no root solve or
integration is authorized. See
`docs/dd_086_condenser_phase_stability_architecture_20260718.md`.

2026-07-18 saturated-liquid numerical result: DD-087 executes once from
frozen contract commit `69101d1`. The canonical live bubble seed is
`117.8164 F` with `Q_C=-55.0036 MMBTU/h`. Both frozen states retain full
`40/40` rank at `h` and `h/2`; the worst condition is `2.45e6`, each local
bubble block is rank `3/3`, conservation is near `1e-16`, and `Q_C` couples
only to the reflux-drum energy row. The independent TP flash classifies the
canonical boundary as near-bubble (`beta=4.46e-4`), not stable vapor. The
canonical residual remains `0.398`, led by Francis hydraulics, so no root is
claimed. One bounded `40 x 40` root campaign may be drafted and precommitted;
execution and dynamics remain unauthorized. See
`docs/dd_087_condenser_saturated_liquid_numerical_audit_20260718.md`.

2026-07-19 saturated-liquid root result: DD-088 executes once from frozen
contract commit `99c9973`. All three starts converge to one root within
`7.54e-11` physical difference, with residual at most `2.32e-14`, rank
`40/40`, local bubble rank `3/3`, condition about `1.16e3`, negative
`Q_C=-52.516 MMBTU/h`, ordered temperatures, no active bound, and roundoff
conservation. The direct bubble equations close near `1e-15`, and the TP
diagnostic remains near-bubble (`beta=6.44e-4`), but
`max|y_bubble-normalize(K*x)|=1.467e-5` exceeds the frozen `1e-5` cross-API
limit. Per the precommitted hard stop, DD-088 fails and this five-volume
solved-duty saturated-liquid architecture is retired without tolerance,
solver, bound, duty, topology, or dynamic variation. See
`docs/dd_088_condenser_saturated_liquid_steady_root_20260719.md`.

2026-07-19 provider-interface result: DD-089 preserves DD-088 as failed and
investigates only the DWSIM PR property interfaces. Three fresh processes are
exactly repeatable. The failed DD-088 metric applied flash-derived `K` to
overall `z`, although those `K` values are exactly `y_flash/x_flash`; the
resulting composition-basis term is `5.747e-5`. A separate direct-bubble
versus TP-flash vapor difference is `4.280e-5`, and the opposing vectors
partially cancel to the observed `1.467e-5`. Flash phase algebra and the lever
rule close at roundoff. A parameter-aligned independent PR implementation
agrees with the direct bubble within `3.83e-5 F` and `4.34e-9` composition.
Prospective architectures shall treat direct fugacity equilibrium as primary
and interpret TP-flash output on its returned phase bases. This finding does
not revive DD-088 or authorize dynamics. See
`docs/dd_089_dwsim_pr_interface_consistency_20260719.md`.

2026-07-19 provider-authority result: DD-090 passes a prospective property
ownership contract without live property or column execution. Direct
imposed-phase fugacity owns equilibrium and saturation acceptance;
parameter-aligned independent PR is validation-only; TP flash owns phase
classification, phase fraction, phase compositions, and lever-rule closure.
Flash K-values are valid on `x_flash/y_flash` bases. `K_flash*z` is prohibited
as a strict bubble-vapor gate for nonzero beta, direct-y/flash-y equality is
not required, and no interface fallback is allowed. Passing authorizes only a
decision on a separately versioned successor architecture. DD-088 remains
failed and dynamics remain unauthorized. See
`docs/dd_090_pr_provider_authority_20260719.md`.

2026-07-19 Core V3 structural result: DD-091 establishes the separate
`dynamic_distillation.core_v3` namespace and the formal
"Provider-Governed Energy-Owned Equilibrium Architecture." Its three-component
steady ledger has `40` unknowns, `40` residuals, structural rank `40`, nullity
zero, no empty row or column, and exact internal component and energy
telescoping. Direct DWSIM imposed-phase fugacity owns stage and condenser
equilibrium; declared DWSIM phase properties own enthalpy and density; TP
flash is diagnostic-only; independent PR is validation-only. The registry
rejects mixed `K_flash*z` use, TP flash in governing equilibrium rows,
independent PR in production residuals, interface fallback, fixed `Q_C`,
duplicate flow ownership, imported profile dependencies, Core V2 residual
ownership, and DD-088 acceptance inheritance. DD-091 makes no property call,
residual evaluation, solve, root import, mass-matrix derivation, or dynamic
integration. It authorizes only one precommitted DD-092 live residual,
provider-ownership, conservation, and Jacobian audit. See
`docs/dd_091_core_v3_provider_governed_architecture_20260719.md`.

2026-07-19 Core V3 live numerical result: DD-092 passes its single execution
from frozen contract commit `1ffa504`. The separately implemented Core V3
residual evaluates two complete precommitted states with live DWSIM PR. Both
uncolored Jacobians retain rank `40/40` at `h=1e-5` and `h/2=5e-6`, every
local condenser bubble block retains rank `3/3`, and the worst condition is
`2.733414e6`, below the `1e8` hard stop. Component and energy telescoping
remain near machine precision, direct bubble fugacity closes near `1e-15`,
TP-flash phase algebra is internally coherent with `beta` about `4.46e-4`,
and validation-only independent PR agrees within `3.61e-5 F` and `1.33e-9`
composition. All `7,234` recorded property requests obey their declared
ownership, with no fallback, projection, mixed-basis gate, or cross-interface
equality gate. The diagnostic scaled residual remains about `0.397`, led by
the expected source-profile versus Francis-hydraulics mismatch; DD-092 is a
numerical-readiness pass, not a steady-root claim. One separate bounded
three-start Core V3 root contract may be drafted. Root execution, mass-matrix
work, and dynamics remain unauthorized. See
`docs/dd_092_core_v3_provider_governed_numerical_20260719.md`.

2026-07-19 Core V3 root-contract boundary: DD-093 defines one future
three-start bounded trust-region campaign on the unchanged DD-092 residual.
It freezes the exact two DD-092 vectors and a fully distinct smooth
five-volume seed whose drum composition, local direct-fugacity bubble, and
negative condenser duty are reconstructed independently. The contract fixes
physical bounds, transformed vectors, comparison scales, solver and Jacobian
settings, result fields, provider rules, and hard stops. No full residual or
nonlinear root solve is used to construct the third seed, and the campaign
has not been executed. Dynamic work remains unauthorized. See
`docs/dd_093_core_v3_steady_root_contract_20260719.md`.

2026-07-25 DD-093 execution result: the one frozen attempt exits during
first-start report assembly because `movement_by_family()` accesses the
scalar `layout.distillate` index as `layout.distillate.start`. The exception
occurs after the first solve and endpoint audits in the frozen control flow,
but before their values are returned or serialized. Starts 2 and 3 do not
run, so no root-existence, reproducibility, or common-root conclusion is
available. The reporting defect is not evidence against the Core V3
equations, but the campaign cannot pass without its required evidence. Per
the contract, it is not patched and rerun. DD-092 remains a readiness pass;
root acceptance, structural dynamic-DAE work, and integration remain
unauthorized. See `docs/dd_093_core_v3_steady_root_20260725.md`.

2026-07-25 reporting-recovery boundary: the user authorizes DD-094 as an
explicit governance exception to DD-093's procedural stop. The only model
code change corrects scalar product and condenser-duty coordinate access in
movement reporting. Direct regression assertions and a complete analytic
`execute_start()` reporting smoke test are added. The generated successor
contract copies every DD-093 mathematical field under checksum
`272890348b11b0164bb4ad506c97178a7565cf712677b51635d7e0c2feb01b93`.
Equations, starts, bounds, scales, solver, tolerances, provider authority, and
acceptance gates are unchanged. DD-094 must be committed before its one
execution; dynamics remain unauthorized. See
`docs/dd_094_core_v3_reporting_recovery_contract_20260725.md`.

2026-07-25 accepted Core V3 root: DD-094 executes once from frozen commit
`52f132d` and passes every gate. Canonical, DD-092-perturbed, and fully
independent smooth starts converge to one physical root with maximum pairwise
normalized difference `2.47414e-10`. Final scaled residuals range from
`2.89e-15` to `7.43e-11`; all endpoint Jacobians retain rank `40/40`, local
bubble rank `3/3`, and worst condition `1373.6911`. The root is interior,
conservative, pressure-prescribed, phase-valid, and provider-compliant, with
`Q_C=-52.515728 MMBTU/h` and drum temperature `133.713 F` below the supplying
stage at `154.422 F`. This establishes steady feasibility for the reduced
provider-governed architecture. Only a structural dynamic-DAE contract is
authorized next; mass-matrix coding and integration remain unauthorized. See
`docs/dd_094_core_v3_steady_root_20260725.md`.

2026-07-25 reduced dynamic contract: DD-095 qualifies DD-094 as a physical
five-volume feasibility root rather than a production design point. Its drum
is `133.713 F`, `15.897 F` warmer than the frozen source because its liquid is
only `0.7030` propane versus `0.9057` in the source. The first dynamic ledger
therefore uses the root only to test equation architecture. Under prescribed
pressure, negligible resident vapor holdup, and full saturation, temperature
and stored liquid energy are functions of component inventory; adding an
independent `U` coordinate would duplicate the thermodynamic constraint.
DD-095 uses `15` component-inventory coordinates, derives `dU/dt` through a
provider-consistent chain rule, and solves `15` derivatives plus `23`
algebraic variables through a structurally full-rank `38 x 38` implicit
ledger. DD-094 `D/B` are fixed for the first open-loop audit; terminal amount
constraints and controllers are absent. A separately frozen live
leading-Jacobian and consistent-derivative audit is required before any
numerical mass matrix or integration. See
`docs/dd_095_core_v3_dynamic_dae_contract_20260725.md`.

2026-07-25 live dynamic numerical contract: DD-096 freezes one evaluation of
the DD-095 implicit system at the exact DD-094 root and zero inventory rate.
The implementation reconstructs saturated-liquid storage from direct-fugacity
bubble states, DWSIM liquid enthalpy, and DWSIM liquid density, then forms the
chain-rule `dU/dt`. It checks the `38 x 38` leading Jacobian at `1e-5` and
`5e-6`, numerical rank, conditioning, singular-spectrum stability, exact
registered coupling, conservation, and provider provenance. Preparation and
execution contain no nonlinear state solve or time integration. A pass may
authorize only a separately frozen implicit-solver contract; a failure stops
this fixed-pressure saturated-liquid dynamic path. See
`docs/dd_096_core_v3_dynamic_dae_numerical_contract_20260725.md`.

2026-07-25 live dynamic numerical result: DD-096 executes once from frozen
commit `42975bc` and passes every gate. The zero-rate root residual is
`2.462658e-11`; the provider-derived storage gradient changes by only
`8.669536e-10` between steps and all bubble reconstructions close below
`4.67e-15`. Both leading Jacobians retain rank `38/38`, worst condition
`35.408732`, no zero or off-registry coupling, and singular-spectrum change
`3.512314e-7`. Component and energy conservation remain near machine
precision across `6306` provider-compliant calls. This authorizes one frozen
implicit-solver contract only. No integration has been performed. See
`docs/dd_096_core_v3_dynamic_dae_numerical_20260725.md`.

2026-07-25 implicit-step contract: DD-097 freezes the first numerical
backward-Euler endpoint solve for Core V3. Fifteen dimensionless inventory-rate
coordinates and 23 endpoint algebraic coordinates form one `38 x 38` solve.
The positive exponential inventory map contains no clipping or rate cap, and
the energy rows use exact saturated-liquid storage differences rather than a
frozen linear storage approximation. Nested direct-fugacity bubble, liquid
enthalpy, and liquid-density calls are explicitly recorded as governing.
The one authorized execution contains a zero-rate algebraic recovery and
independent `1.0 s` and `0.5 s` checks from DD-094. It is not a trajectory or
disturbance test. See
`docs/dd_097_core_v3_implicit_step_contract_20260725.md`.

2026-07-25 implicit-step result: DD-097 executes once from frozen commit
`ac43127` and passes every gate. Zero-rate algebraic recovery retains rank
`23/23` and condition `12.20`. Independent `1.0 s` and `0.5 s` backward-Euler
steps retain rank `38/38`, condition below `35.2`, scaled residual below
`1.1e-12`, physical states, and discrete component/energy errors below
`2.5e-13`. Step refinement is near `1e-12`; all `44,686` governing DWSIM
calls pass without fallback. These stationary-root checks validate the step
machinery but do not yet exercise nonzero transient motion. One frozen short
open-loop trajectory contract is authorized next. See
`docs/dd_097_core_v3_implicit_step_20260725.md`.

2026-07-25 short open-loop contract: DD-098 freezes the first multi-step and
nonzero-motion Core V3 test. It contains a `2.0 s` unchanged-input root hold
and independent `2.0 s` trajectories at `dt=1.0 s` and `0.5 s` after a sole
`+0.1%` feed-throughput step. Scaling feed component rates and total enthalpy
together preserves composition and specific enthalpy. Duties, products,
pressure, geometry, and DD-097 solver settings remain fixed. Every endpoint
is fail-fast and must retain rank, physicality, discrete conservation, and
provider ownership. Global total accumulation has an analytic target because
feed and product totals are fixed. See
`docs/dd_098_core_v3_short_open_loop_contract_20260725.md`.

2026-07-25 short open-loop result: DD-098 executes once from frozen commit
`5ded9f6` and passes all eight requested endpoints. The root hold remains
stationary. Both `+0.1%` feed-step trajectories accumulate exactly
`0.003968319 lbmol` over `2 s`, within `1.29e-11` relative of the external
balance. Every endpoint remains rank `38/38`, condition below `35.2`, physical,
and conservative. The `1.0 s`/`0.5 s` endpoints agree within `2.63e-6`
relative inventory, `4.46e-6` algebraic coordinates, and `1.06e-5 F`.
Execution requires `325,332` provider calls and `139.236 s`, so this is a
correctness reference rather than a production-speed integrator. One modest
longer open-loop contract is authorized. See
`docs/dd_098_core_v3_short_open_loop_20260725.md`.

2026-07-25 performance correction: DD-099 removes the five nested bubble
reconstructions formerly performed inside every backward-Euler residual. The
governing property packet now includes liquid density for all five volumes,
and internal-energy storage uses the same trial-state enthalpy and density as
the governing equations. A backward-Euler-specific structural pattern includes
the rate-to-endpoint-inventory chain and colors 38 columns into 17 groups,
reducing central Jacobian evaluations from 76 to 34. In one frozen execution,
colored and uncolored stationary/feed-step endpoints and Jacobians are
identical to reported precision; all gates pass; no nested bubble call occurs;
and mean calls fall from `40,666.5` to `3,000` per endpoint (`13.56x`). The
actual trial-state Jacobian condition is about `1.83e5`, still full rank and
below `1e8`. One modest longer open-loop contract is authorized. See
`docs/dd_099_core_v3_performance_20260725.md`.

2026-07-25 longer open-loop result: DD-100 executes 35 colored-Jacobian
backward-Euler endpoints from frozen contract commit `d92d354`: a `5 s` root
hold and independent `10 s` `+0.1%` feed steps at `dt=1.0 s` and `0.5 s`.
Every endpoint is rank `38/38`, physical, conservative, and below the residual
and equilibrium limits; worst condition is `7.39e5`. Both disturbed runs match
the exact `0.0198415944 lbmol` accumulation within about `1e-11` relative.
Refined endpoints differ by `4.31e-6` relative inventory, `6.81e-6` algebraic
coordinates, and `1.61e-5 F`. Runtime is `69.264 s` for `130,368` calls, or
`3,724.8` per endpoint, with no nested bubble reconstruction or fallback. The
next change must be a separately frozen dynamic-scope decision; pressure,
vapor-holdup, controller, and production-horizon claims remain unauthorized.
See `docs/dd_100_core_v3_longer_open_loop_20260725.md`.

2026-07-25 pressure-layer structural decision: DD-101 keeps reflux-drum
pressure as the sole anchor and promotes the other four volume pressures to
simultaneous algebraic unknowns. Four generic dry-tray-plus-liquid-head
pressure-drop equations close the same four vapor links whose rates remain
energy-owned. The resulting three-component implicit ledger is `42 x 42`,
structural rank `42`, and nullity zero, with no unused or unregistered entry.
Governing pressure drop will require declared liquid density and direct vapor
compressibility `Z`; no TP flash, ideal-gas substitution, stale property,
conductance owner, profile, cap, relaxation, or fallback is authorized. DD-101
performs no live property call or solve. One frozen live residual/Jacobian audit
is the only next authorization. See
`docs/dd_101_core_v3_pressure_layer_contract_20260725.md`.

2026-07-25 pressure-layer numerical result: DD-102 executes the frozen live
audit once from contract commit `b958d00`. The accepted profile and fixed
ordered perturbation retain rank `42/42` at both finite-difference steps, with
worst condition `162.783`, spectrum change below `3.51e-7`, exact registered
coupling, and roundoff conservation. All `9,465` provider calls pass in
`8.950 s`. The accepted fixed-pressure profile is not hydraulically consistent:
its four pressure residuals are `[1.366, 2.513, 4.444, 3.886] psi`. This is a
reported starting residual, not a failed numerical gate. One separately frozen
pressure-layer steady-root contract is authorized. It must explicitly decide
whether the reduced bottom vapor link owns the selected bottom stage's tray
geometry, because the source workbook declares no independent reboiler/sump
pressure-drop geometry. Pressure dynamics, vapor holdup, controllers, and
integration remain unauthorized. See
`docs/dd_102_core_v3_pressure_layer_numerical_20260725.md`.

2026-07-07 status note: broad residual reweighting is not the current acceptance path. Recent top-liquid alignment, vapor-flow ceiling, and vapor-flow/energy residual-objective probes showed that a targeted residual can improve while the dynamic launch and physical audit get worse. Treat those knobs as diagnostics for the energy/vapor-flow closure review, not as accepted initialization mechanisms.

Historical 2026-07-08 status note, superseded by DD-075/DD-076: the
bounded C3/C4 checkpoint was treated as a regression baseline while a broader
implicit solve remained under consideration. DD-075 subsequently retired that
full-system path, and DD-076 replaces it with a clean derivation-first model.

2026-07-08 sequencing note: before committing engineering time to an implicit simultaneous solve, run the longer baseline gate and a focused vapor-material audit on the localized no-energy/checkpoint residual family. Recent history shows several apparent architecture problems were actually concrete consistency bugs in the current explicit path.

2026-07-08 longer-gate result: the 1800 s extension of the current best C3/C4 recipe failed after the 900 s window. The failure turns on around 1200-1240 s near the generic feed-adjacent interface: stage 12/13 vapor transport terms and energy residuals activate while the no-lag energy vapor-flow calc/used mismatch remains zero. This keeps the focus on runtime coupling and term ownership in the existing model before any broad implicit architecture rewrite.

2026-07-12 equilibrium-gate correction: raw `K_state=y/x` cannot generally be compared directly with raw thermo `K` because vapor targets are normalized by `sum(K*x)`. Model-health claims require the rate gate plus normalized interior `y-y_target` consistency. `tools/audit_k_state_drift.py` retains raw-K context but no longer treats it as the physical acceptance metric.

2026-07-12 tray-flow ownership finding: DD-058's section-wise liquid-flow
plateaus are a structural consequence of profile-blended liquid hydraulics
plus composition-only equilibrium transfer at fixed phase totals. DD-060
proved that directly applying a full fixed-T/P flash phase target is not an
energy-conserving remedy. DD-076 retains conserved component/energy ownership
but no longer attempts to add phase split, hydraulic pressure, and vapor
inventory simultaneously. Those layers now have separate authorization gates.
See `docs/dd_060_physics_owned_tray_flow_probe_20260712.md`.

2026-07-08 equilibrium-transfer guard tradeoff: the component-transfer guard is now a central coupling issue. Multiplier `1.0` suppresses the dynamic vapor wave better but leaves persistent K drift; multiplier `1.5` improves K consistency but worsens the rate-based wave. This argues for a root-cause review of the guarded equilibrium-transfer formulation and its transport inputs before promoting either setting as the runtime default.

## 1) Scope

Primary execution path:
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- `src/dynamic_distillation/column_rhs_v1.py`

Primary inputs:
- Excel case file (`Specifications`, `Initial Conditions`, optional `Components`, optional `Streams`)

Primary outputs:
- `logs/column_summary_<run_id>.csv`
- `logs/column_profile_<run_id>.csv`
- `logs/<run_folder>/<input_stem>__restart_<run_id>.xlsx`
- `logs/run_registry.csv`
- regenerated ledgers in `docs/experiment_ledger.csv` and `docs/experiment_ledger.md`

## 2) Top-Level Module Map

- `excel_case_loader_v1.py`
Loads workbook content into `CaseData` (components, specs, initial profiles, streams).

- `column_spec_builder_v1.py`
Builds immutable `ColumnSpec` (profiles, geometry expansion, stream normalization, simulation defaults).

- `excel_case_validator_v1.py`
Validates loaded case before simulation starts.

- `state_vector_layout_v1.py`
Defines deterministic state vector layout and pack/unpack functions.

- `dynamic_run_scaffold_v1.py`
Owns startup initialization, control updates, runtime mode resolution, integration loop (explicit or stiff), logging, run registration.

- `column_rhs_v1.py`
Computes `dydt` and diagnostics for mass/energy/hydraulics/pressure/thermo closures.

- Thermo providers:
`thermo_provider_v1.py` (live backend),
`thermo_surrogate_v1.py` (tabular single-process),
`thermo_table_pool_v1.py` (tabular process pool).

- `experiment_ledger_v1.py`
Appends run records and rebuilds human-readable ledger artifacts.

## 3) Data Objects And State

- `CaseData`: loader-level workbook payload.
- `ColumnSpec`: normalized model case used by runner and RHS.
- `StateVectorLayout`: declares vector slices and optional state blocks.
- `ColumnInputs`: per-step runtime inputs into RHS (boundary flows, model toggles, cached seeds, closures).

State vector blocks are configurable through layout flags:
- tray liquid holdup components (`tray_L`)
- tray vapor holdup components (`tray_V`)
- top and bottom holdup vectors (`top_L`, `top_V`, `bottom_L`, `bottom_V`)
- optional tray temperature states (`tray_T_f`, `bottom_T_f`)
- optional tray energy states (`tray_EL_BTU`, `tray_EV_BTU`)

## 4) Runner Execution Pipeline

Runner entrypoint:
- `run_smoke_simulation(cfg)` in `dynamic_run_scaffold_v1.py`

High-level flow:
1. Load and validate case.
2. Build `ColumnSpec`.
3. Build `StateVectorLayout`.
4. Build base `ColumnInputs` and thermo provider.
5. Initialize state:
- pack initial holdups/compositions
- initialize vapor holdup from pressure profile
- optional startup thermo conditioning
- optional top-drum startup steadying
- initialize startup/runtime thermo diagnostics and reusable thermo packets when enabled

Fresh-startup note:
- A "fresh" run means the Excel input does not include explicit runtime restart sheets.
- On this column, a full fresh startup has recently taken about `10-12 minutes` of wall-clock time before the first logged integration row appears.
- That time is spent in pre-integration conditioning, especially vapor-holdup initialization from startup pressure, thermo-consistent startup conditioning, and top-drum startup steadying.
- These passes are important because they reduce pressure/holdup/thermo mismatch at `t=0`. When they are skipped or weakened, the model may start faster but the early dynamic trajectory can diverge materially from the fully conditioned path.
- `--fast-startup` is now the aggressive shortcut: it skips startup thermo conditioning, skips hydraulic-energy startup consistency, and skips top-drum startup steadying.
- When explicit runtime restart sheets are present, the runner can skip most of this fresh-startup work and move much more directly into integration.
- Before normal logging begins, restart runs now apply a short hidden re-entry settling pass to reduce the immediate pressure/composition bump that would otherwise appear on the first resumed steps.

Top-drum startup inventory precedence:
- if explicit top liquid holdup is provided (`Top Accumulator Holdup (lbmol)` and aliases), that value is treated as authoritative for startup reflux-drum liquid inventory
- `Top Drum Liquid Fraction (-)` remains useful for level/control/display interpretation and geometry-based inference, but it is secondary and is only used to infer startup liquid inventory when explicit top holdup is absent
6. Build optional controllers (level, pressure, distillate composition, bottoms composition).
7. Time loop (`step = 0..n_steps`):
- update step boundary commands and control MVs
- resolve runtime mode and startup sequence behavior
- snapshot thermo counters/timed buckets into run metadata and diagnostics
- resolve effective integrator profile (including hydraulic+IDA tuned defaults when legacy defaults are unchanged)
- gate thermo refresh by cadence/threshold logic
- build per-step `ColumnInputs` including previous-step cached signals
- evaluate RHS: `dydt, diag = column_rhs(...)`
- log diagnostics
- time update:
  - explicit mode: `y = y + dt * dydt`
  - stiff modes: per-step `solve_ivp` (`BDF` or `Radau`) with explicit fallback on step failure
  - ida mode: implicit-Euler fixed-point stepper with RHS-coupled DAE algebraic closure; convergence uses state-update error plus weighted algebraic residual checks when those residuals are available
- cache diagnostics for next step
8. Write run artifacts and update experiment ledger.

## 5) RHS Architecture

RHS entrypoint:
- `column_rhs(t, y, col, layout, inputs)` in `column_rhs_v1.py`

Major stages inside RHS:
1. Unpack state and normalize compositions as needed.
2. Build feed split and boundary flows.
3. Build internal liquid flow:
- profile baseline from `ColumnSpec`
- optional Francis-weir hydraulic override on internal stages.

Current practical meaning in the hydraulic parity branch:
- `L_out_used` is the liquid flow actually marched by the model.
- `L_out_hyd` is the Francis/weir hydraulic candidate.
- when liquid-hydraulic override is disabled, `L_out_hyd` is diagnostic only and may differ materially from `L_out_used`.
4. Build vapor flow based on `vapor_flow_model`:
- `profile`: use profile traffic
- `conductance`: pressure-conductance closure with clamps/relaxation
- `energy`: tray energy-based closure with clamps/relaxation.
5. Build pressure based on `pressure_model`:
- `spec`: use case profile
- `hydraulic`: compute hydraulic tray profile and top-drum coupling.
6. Apply condenser split and top-drum pressure gate logic.
7. Assemble component derivatives and optional energy derivatives.
8. Perform thermo refresh/cache update and equilibrium-relaxation terms.
9. Emit diagnostic dictionary (flows, pressures, residuals, control PVs, closure signals).

### Total-Condenser Topology Requirement

For a total condenser, the model topology should distinguish the top tray from the condenser/reflux-drum boundary:

- vapor leaves the top active tray and enters the condenser boundary,
- condenser duty is applied in the condenser boundary calculation,
- fully condensed overhead liquid enters the reflux drum/top accumulator,
- reflux and distillate are liquid draws from the reflux drum,
- the total condenser is not treated as a separating equilibrium tray with its own post-condenser vapor holdup.

Requirement `DD-033`: total-condenser duty and condensed-liquid energy must not be owned by a tray liquid-energy state that has zero liquid holdup. If a workbook maps stage 1 as a dry/zero-holdup total-condenser boundary, the RHS should either:

- route condenser energy to an explicit top-drum/condenser energy state when boundary states are enabled, or
- treat condenser energy algebraically as a boundary duty/enthalpy calculation and omit the zero-holdup tray energy derivative.

This requirement is separate from the strict total-condense mass-split rule. A run can enforce zero vapor slip to the top drum and still have the wrong energy owner if condenser duty is deposited into `tray_EL_BTU[0]` while `ML_stage1 = 0`.

Implementation note: `column_rhs_v1.py` now treats a dry stage-1 total condenser as an algebraic condenser-boundary energy case in the B1 energy path. In that case, condenser duty is not deposited into `tray_EL_BTU[0]`; reflux/liquid transport uses the condensed-liquid enthalpy from the condenser packet, or a fallback enthalpy computed from the total-condenser duty relation. This is a partial `DD-033` implementation, not the final explicit reflux-drum energy model.

## 6) Coupling Behavior (Important)

Current architecture is sequential inside each RHS call, not fully simultaneous:

1. Vapor flow (`V_out`) is computed first.
2. Hydraulic pressure (`P_tray_hyd`) is computed later in the same RHS call.
3. Runner caches pressure and feeds it back as `P_tray_prev` on the next timestep.

Implication:
- Pressure-vapor coupling is effectively one-step lagged in explicit time marching.
- This is a key reason stiff `P/V` interactions can require damping or additional safeguards.
- In hydraulic+energy operation, increasing reboiler duty does not guarantee a same-step
  increase in vapor molar traffic (`V_out`); coupled temperature/enthalpy, pressure,
  and limiter dynamics can produce duty-up / vapor-down behavior.
- Recent initialization probes showed that reducing a local vapor-flow mismatch or
  a residual-solver objective is not sufficient evidence that this coupling is
  dynamically consistent. The acceptance signal is the residual audit plus a
  short dynamic gate, not the optimizer norm alone.

Optional mitigation now available in runner:
- inner fixed-point `P/V` coupling per timestep (`--pv-inner-max-iter` with
  `--pv-inner-p-tol-psia` and `--pv-inner-v-tol-lbmolph`).
- this is applied only when pressure mode is hydraulic and vapor-flow mode is
  energy or conductance.

## 7) Runtime Modes

Configured via `--runtime-mode` in `dynamic_run_scaffold_v1.py`.

- `parity`:
forces pressure spec + vapor profile + liquid hydraulics override off.

- `calibration`:
uses the same closure set as `parity` (pressure spec + vapor profile + liquid hydraulics override off), with explicit parity-calibration intent.

- `hydraulic`:
forces hydraulic pressure + energy vapor closure.

Current project convention for ChemSep parity work:
- liquid-hydraulic override is kept off unless explicitly requested
- this keeps the seeded/profile liquid traffic active while still logging `L_out_hyd` for hydraulic diagnosis

- `legacy`:
uses Excel/CLI-driven behavior and is the only mode where startup hydraulic sequencing is active.

## 8) Control Architecture

Controllers are implemented in runner, not inside RHS:
- level control:
top drum holdup or true level -> distillate draw,
bottom sump holdup or true level -> bottoms draw.

Bottom true-level mode:
- uses sump liquid holdup plus liquid density to estimate live sump liquid volume
- interprets sump level as a vertical cylindrical vessel fraction when sump total volume is provided

Bottom-end topology in the standard explicit-sump model:
- liquid from the bottom tray drains into the bottoms sump
- bottoms product is drawn from the sump
- reboiler liquid feed is also taken from the sump
- reboiler boilup returns vapor to the bottom tray

Current exception:
- the special no-holdup reboiler shortcut still uses its legacy feed path until
  an explicit sump-circulation model is added there

- pressure control:
top pressure PV -> condenser duty or top-pressure anchor MV.

- composition control:
distillate composition -> reflux MV,
bottoms composition -> boilup or reboiler-duty MV.

Bottoms composition MV semantics:
- `--bottoms-comp-mv boilup`: active MV is boilup flow (`Boilup_cmd_lbmolph`).
- `--bottoms-comp-mv reboiler-duty`: active MV is reboiler duty
  (`Q_reb_cmd_BTUph`, with `Q_reb_used_BTUph` as realized duty).
- In reboiler-duty mode, `Boilup_cmd_lbmolph` is expected to be `NaN` in logs.

Control sequence:
- controllers are evaluated each step using latest cached PV/diag signals.
- resulting commands are passed into RHS through step-local `BoundaryFlows`/`ColumnInputs`.

## 9) Thermo Architecture

Thermo modes:
- `stub`
- `dwsim`
- `table`
- `table-pool`

Batch thermo refresh:
- RHS uses batch path when provider supports `flash_TP_full_batch(...)`.
- `table-pool` parallelizes only batch flash rows; scalar helper calls remain local.

Pool performance is workload-dependent:
- effective throughput depends on rows refreshed per step and chunking.
- more workers do not guarantee faster runtime if task granularity is small.

Current project guidance for this column configuration:
- use `--thermo table-pool` and tune `--thermo-pool-workers` to hardware and run
  size (start around `2..6`; higher counts are not always faster).

## 10) Logging, Traceability, And Reproducibility

Per run:
- profile CSV with stage-level and node-level diagnostics.
- summary CSV with global and top-level metrics plus per-step integrator diagnostics (`integrator_*`, `ida_*` fields).
- restart workbook copied from the input case file and updated with final dynamic state:
  - `Initial Conditions`
  - `Boundary State`
  - `Energy State`
  - `Controller State`
  - `Dynamic Memory`

Restart-workbook intent:
- The base workbook remains the case definition.
- The restart workbook is the continuation artifact.
- Using the restart workbook for a follow-on run allows the model to start from the reached dynamic condition and avoid repeating most of the expensive fresh-startup calculations.

K-value diagnostics in profile CSV:
- `K_state_<comp>`: instantaneous dynamic-state ratio `y/x` on the tray.
- `K_thermo_<comp>`: thermo-flash equilibrium K at tray `T,P,z`.
- `K_state_over_K_thermo_<comp>`: disequilibrium indicator; near `1.0` means state
  is close to thermo equilibrium.

### 10.1) Common Misreads

- `Boilup_cmd_lbmolph` being `NaN` is expected when bottoms MV is `reboiler-duty`;
  in that mode, use `Q_reb_cmd_BTUph` and `Q_reb_used_BTUph` as the active MV traces.
- `K_thermo_<comp>` and `K_state_<comp>` are different signals:
  thermo equilibrium K versus dynamic state `y/x`.
- A rising `Q_reb_*` command does not by itself prove actual vapor molar flow increased;
  verify with stage `V_out_lbmolph` trends.

Registry and ledger:
- each run is recorded in `logs/run_registry.csv` with command provenance.
- documentation ledgers are regenerated in `docs/experiment_ledger.csv` and `docs/experiment_ledger.md`.

Duplicate command identity:
- command identity normalization is applied for duplicate guard behavior.

## 11) Known Architectural Constraints

- Default integrator is explicit Euler (timestep-sensitive); optional per-step stiff modes (`BDF`/`Radau`) and pilot `IDA` fixed-point mode are available.
- `P/V` coupling is sequential with previous-step feedback, not full-step simultaneous.
- Full simultaneous (large implicit nonlinear solve) is not the current architecture.
- Optional pilot algebraic Newton solve for `z=[P_tray, V_out]` can be enabled,
  but this is still a pilot path and not yet a full system-level DAE solve.
  In stiff integrator mode, this pilot solve is executed once per outer step,
  while implicit substeps use the PV-coupled RHS with seeded algebraics.
- Hydraulic vapor-flow clamps are still limiter-based; stiff-mode RHS now supports
  optional smooth clamp regularization to reduce derivative kinks near limits.
- `--dynamic-vflow-nominal-hi-ratio` and the initializer's
  `--vflow-energy-closure-weight` are diagnostic levers. Current evidence does
  not support using them as fixes without an energy/vapor-flow topology change.
- Startup initialization quality strongly affects early transient stiffness.

## 12) Future Architecture Options

The former option to broaden the existing runtime into one large implicit
solve is retired by DD-075. The selected future architecture is the isolated
equilibrium-DAE v2 contract in
`docs/dd_076_equilibrium_dae_v2_architecture_contract_20260718.md`.

DD-077 through DD-081 completed the bounded structural, source-equation,
one-volume, and five-volume pre-solve gates. DD-082 then failed the required
common physical-root gate at a reproducible component-balance floor with one
active transformed-coordinate bound. The current Gate C operating
specification is retired. Energy-determined vapor traffic, pressure dynamics,
vapor holdup, controllers, production integration, and another solver variant
remain unauthorized.

2026-07-26 Core V3 pressure-layer steady-root decision: DD-103 resolves the
reduced bottom-boundary ownership by treating the combined reboiler/sump
return as a dry-resistance-only link; only the three physical tray links
receive liquid head. It then fixes all 15 conserved inventory rates at zero
and solves 27 algebraic coordinates against the 42 pressure-enabled steady
equations from two predefined starts. Both solves terminate at nearly the same
positive, ordered profile near `218.44-218.66 psia`; the pressure equations
close to about `2.1e-5 psi`, both endpoint Jacobians have column rank `27/27`,
worst condition is `65.959`, and conservation/provider gates pass.
Nevertheless, the full scaled residual stalls near `8.947e-3`, and the
endpoints miss the frozen common-root limit. The fixed DD-094 inventories
therefore cannot be reconciled into an exact pressure-enabled steady state by
algebraic movement alone. This retires algebraic-only pressure repair. The
next architectural increment may only define simultaneous pressure-enabled
implicit-DAE ownership in which conserved inventories and rates participate;
numerical stepping and integration remain unauthorized.

2026-07-26 Core V3 pressure-enabled implicit-DAE decision: DD-104 restores
the 15 component-inventory rates as simultaneous unknowns beside the 27
algebraic coordinates of the pressure layer. This produces the natural square
`42 x 42` implicit system that DD-103's frozen-inventory `42 x 27` repair did
not permit. Structural rank is `42`, nullity is zero, and every backward-Euler
rate-to-endpoint-inventory dependency is registered. Reflux-drum pressure is
the sole anchor; four lower pressures are algebraic; no pressure rate or vapor
inventory is added. The combined reboiler/sump return is dry-only, while three
physical tray links retain liquid head. The deterministic solve pattern uses
20 conflict-free colors. No property evaluation, numerical solve, mass-matrix
evaluation, or integration occurred. One frozen live pressure-enabled
leading-Jacobian and consistent-rate audit is authorized next.

2026-07-26 Core V3 pressure-enabled first-step result: DD-105 replaces the
inapplicable fixed-pressure storage gradient with exact live endpoint energy
storage and solves independent `1.0 s` and `0.5 s` backward-Euler first steps.
Both endpoints close below `9.0e-13`; all four Jacobians are rank `42/42`,
well conditioned relative to the gate, conservative, physical, and provider
compliant. They do not refine to one state: inventory differs by `6.28%`,
algebraic coordinates by `1.67`, and pressure by `2.77 psi`. DD-094 is
therefore not a consistent initial state for the pressure-enabled model, and
the first step would embed an arbitrary timestep-dependent pressure/energy
handoff. Pressure-enabled stepping is stopped before a trajectory. Any
successor initializer must move conserved states under explicit global
component/energy constraints and terminal-inventory ownership.

2026-07-26 Core V3 pressure-consistent initializer structure: DD-106 removes
the timestep from initialization and registers one equality-constrained
selection problem over 15 positive component inventories, 15 continuous
inventory rates, and 27 pressure-enabled algebraic variables. The 42 DD-104
DAE rows remain exact. Three component-total constraints, one live stored-
energy-total constraint, and two terminal total-holdup constraints bring the
ledger to 48 independent equalities over 57 primal variables. Structural rank
is 48, leaving nine selection degrees of freedom. A diagonal normalized
minimum-rate/minimum-movement objective produces a full-rank `105 x 105` KKT
pattern. Drum and sump total inventories are held to DD-094 values, while
their compositions remain free. No property call or solve occurred. One
separately frozen live numerical initializer contract is authorized; a
timestep, trajectory, controller, and integration remain unauthorized.

2026-07-26 Core V3 initializer numerical-readiness decision: DD-107 stops the
DD-106 live numerical successor before implementation or DWSIM execution.
DD-106 permits nonzero `dN/dt` while four lower pressures move algebraically,
but it has no independent `U` states, no `dU/dt` rates, and no pressure-aware
continuous reduced storage derivative. Its inherited exact storage statement
is `U_next-U_previous`, which requires a timestep. DD-096's gradient cannot be
reused because it was derived at fixed pressure. Consequently the five energy
balances cannot be evaluated exactly for the nonzero-rate initializer
objective. Hidden timestepping, fixed-pressure-gradient reuse, and numerical
tuning are prohibited. One property-free conserved-`N/U` plus algebraic-
pressure ownership audit is the only authorized successor.

2026-07-26 Core V3 conserved-energy pressure-DAE decision: DD-108 first tests
independent `U/dU` ownership in all five volumes. That `47 x 47` assembly has
structural rank `46`: fixed drum pressure plus bubble equilibrium already
determines top temperature/storage, so the top storage row duplicates a
constraint and leaves `Q_C` unmatched. The corrected ownership follows
pressure ownership. Top energy remains derived through the exact fixed-
pressure saturation gradient; each of the four lower algebraic-pressure
volumes receives independent `U/dU` and one live enthalpy/density storage
closure. The resulting three-component ledger is `46 x 46`, rank `46`,
nullity zero; a generic two-component ledger is `36 x 36`, rank `36`.
Conservation and single vapor-flow ownership remain intact, with no pressure
rate, vapor inventory, controller, profile, cap, or relaxation. One frozen
live leading-Jacobian and state-manifold numerical contract is authorized.

2026-07-26 Core V3 conserved-energy numerical contract: DD-109 freezes the
first live evaluation of the corrected DD-108 `46 x 46` system. It uses the
DD-094 conserved state with two independently frozen algebraic-pressure
profiles, four explicit lower internal-energy coordinates reconstructed from
the accepted provider basis, and the fixed-pressure drum's exact reduced
storage gradient. Two central-difference steps use a precomputed 15-color
structural grouping, while one full canonical Jacobian independently checks
the colored reconstruction and the registered coupling graph. Full rank,
four-dimensional lower storage-manifold rank, conditioning, spectrum,
conservation, provider provenance, physicality, and strict call/wall limits
are hard gates. Contract preparation performs no live property evaluation.
After commit, exactly one numerical audit is authorized; no root solve,
initializer, state repair, backward-Euler step, or trajectory is included.

2026-07-26 Core V3 conserved-energy numerical result: DD-109 executes once
from frozen commit `99b88fd`. All five leading Jacobians are rank `46/46`;
the four lower storage constraints retain rank `4/4`; worst condition is
`4.30341e5`; colored/full agreement is exact to reported precision; spectra,
storage closure, pressure ordering, conservation, provider ownership, calls,
and runtime pass. The formal result nevertheless fails because the added
physical gate applies tray-height requirements to every volume. Core V3
intentionally records `NaN` tray height for the reflux drum and combined
reboiler/sump, which do not own Francis tray geometry; the three applicable
tray heights are finite and positive. The dry-only terminal pressure link's
zero liquid-head drop is also intentional. The raw failure stands and is not
rerun. This is a gate-scope defect rather than evidence of numerical rank or
state-manifold failure, but further work requires an explicit governance
decision.

2026-07-26 Core V3 DD-109 physical-gate recovery contract: DD-110 uses the
explicit user-authorized reporting-only exception and does not rerun DD-109.
It hashes the frozen DD-109 contract and result, preserves all numerical
values and every unrelated gate, and re-adjudicates only the two failed
physical-reporting gates according to existing ownership. The rectifying,
feed, and stripping volumes must have finite positive Francis tray heights;
the reflux drum and combined reboiler/sump must retain their intentional
`NaN` tray-height sentinels. Liquid-head pressure drop must be positive only
on the three links that own liquid head and zero on the dry-only terminal
link. Any unrelated failure or evidence change is a hard stop. Preparation
performs no property, residual, Jacobian, solve, initializer, or timestep
work. One static adjudication is authorized after the contract commit.

2026-07-26 Core V3 DD-109 physical-gate recovery result: DD-110 executes once
from commit `464e568` and passes. The source DD-109 contract/result hashes are
unchanged, every inherited numerical gate remains true, and the ownership-
aware physical checks confirm three positive Francis tray heights, two
intentional non-Francis terminal `NaN` sentinels, and zero liquid-head drop on
the dry-only terminal link. The adjudication uses zero property, residual,
Jacobian, solver, initializer, or timestep evaluations. This accepts DD-109's
rank/manifold evidence without reclassifying or rerunning its raw result. One
separately frozen conserved-`N/U` pressure-consistent initializer contract may
now be drafted; initializer execution and dynamic stepping remain
unauthorized.

2026-07-26 Core V3 conserved-`N/U` initializer structure: DD-111 replaces
DD-106's incomplete energy ownership with the validated DD-108/DD-109 mixed
energy formulation. The primal contains 15 component inventories, four lower
internal energies, 19 matching rates, and 27 algebraic coordinates. All 46
pressure DAE rows remain exact, including four live lower storage closures;
three component totals, one whole-column energy total, and two terminal total-
inventory constraints produce 52 independent equalities over 65 primals.
Whole-column energy uses derived fixed-pressure top storage plus the four
independent lower `U` states. The feasible manifold has dimension 13, and a
positive normalized selection objective gives a full-rank `117 x 117` KKT
pattern. The two-component generic audit also passes. No property call, solve,
or timestep occurred. One separately frozen live constrained-initializer
contract may be drafted; execution and dynamics remain unauthorized.

2026-07-26 Core V3 conserved-`N/U` live initializer contract: DD-112 freezes
the complete numerical selection campaign without executing it. Sixty-five
coordinates use positive log component inventories, scaled affine lower
energies, validated normalized rates, and the DD-103 algebraic basis. Exact
targets preserve DD-094 component and terminal totals plus DD-096 total stored
energy. Two starts use the DD-094 pressure profile and the DD-103 pressure
endpoint with its DD-109 live storage. One SLSQP equality-constrained solver
uses an analytic `1/10/1` state/rate/algebraic objective and a 21-color central-
difference constraint Jacobian. Both starts must reach one interior physical
optimum satisfying all 52 constraints, rank, conditioning, spectrum,
registered-coupling, KKT, conservation, provider, call, and wall gates. No
penalty relaxation, retry, alternate solver, changed weight, continuation,
timestep, or dynamics is permitted. One execution is authorized only after
the contract commit.

2026-07-26 Core V3 conserved-`N/U` live initializer result: DD-112 executes
once from frozen commit `0f4dac3`. Both SLSQP starts converge to essentially
the same objective, satisfy all 52 constraints below `9e-11`, retain rank
`52/52` with condition about `2.05e3`, and pass the Jacobian, KKT, interior-
bound, pressure, physicality, conservation, provider, call, and wall gates.
The normalized endpoint difference is `1.880119e-6`, above the precommitted
`1e-6` limit; its largest coordinate is a transformed reflux-drum bubble-
composition value. Physical endpoint pressure differs by only `5.56e-8 psia`,
but the frozen gate is controlling. DD-112 is retired without retry or tuning.
No accepted initializer exists, and zero-time audit, timestep, and dynamic
integration remain unauthorized pending an explicit architecture decision.

2026-07-27 Core V3 DD-112 physical-equivalence adjudication contract: DD-113
is a governance-only static successor. It keeps DD-112 formally failed and
does not rerun or retune its optimizer. Immutable source hashes, all inherited
gates other than `common_solution`, engineering-variable scales and limits,
physical composition reconstruction, and deterministic canonical endpoint
selection are frozen before execution. Any unrelated source failure or saved-
endpoint disagreement in inventory, composition, energy, rates, pressure,
temperature, flow, product, or duty stops the path. Contract preparation uses
zero property, residual, Jacobian, solve, initializer, timestep, or dynamic
evaluations. One static execution is authorized only after commit.

2026-07-27 Core V3 DD-112 physical-equivalence adjudication result: DD-113
passes once from frozen commit `5d794bd`. All 15 physical comparison gates
pass; every inherited DD-112 gate is unchanged and true; saved liquid, vapor,
and bubble compositions reconstruct as positive normalized vectors. The
largest inventory difference is `1.706e-6` on its reference scale, liquid and
vapor mole-fraction differences are below `5.55e-7`, pressure differs by
`5.564e-9` on its 10-psi scale, and temperature differs by `5.303e-5 F`.
The lower-objective DD-094-start endpoint is selected canonically. This static
action uses zero property, residual, Jacobian, solver, initializer, timestep,
or dynamic calls. DD-112 remains formally failed; DD-113 authorizes drafting
one frozen zero-time audit of the canonical saved endpoint only.

2026-07-27 Core V3 canonical initializer zero-time contract: DD-114 freezes a
fresh live evaluation of the DD-113-selected 65-coordinate endpoint. The audit
retains all 52 DAE, global conservation, and terminal ownership rows; evaluates
one residual, two 21-color Jacobians at `1e-5` and `5e-6`, and one full
cross-check; and compares the reconstructed engineering state against the
immutable DD-112 endpoint. Rank, condition, spectrum, registry, physicality,
pressure, conservation, provider, `50000`-call, and `180 s` gates are fixed.
Contract preparation performs no property, residual, Jacobian, solve,
initializer, timestep, or dynamic evaluation. One zero-time execution is
authorized only after commit; passing may authorize only a separately frozen
first-step refinement contract.

2026-07-27 Core V3 canonical initializer zero-time result: DD-114 passes once
from frozen commit `6e5538b`. The fresh live residual closes all 52 rows below
`2.02e-12`; two colored and one full Jacobian are rank `52/52` with worst
condition `2.055e3`; spectrum change is `2.91e-6`; and colored/full difference
is zero. The physical endpoint reproduces the DD-112 record exactly, remains
positive and pressure ordered, and conserves component and energy totals at
roundoff. Direct DWSIM PR ownership passes with `6021` calls in `7.395 s`.
The accepted object is a consistent initial state plus its generally nonzero
equation-owned rates, not a steady state. One separately frozen first-step
refinement contract may now be drafted; no timestep or dynamics occurred.

2026-07-27 Core V3 initializer first-step refinement contract: DD-115 adds the
missing conserved-`N/U` backward-Euler kernel for the accepted pressure DAE.
Fifteen component inventories advance through positivity-preserving exponential
coordinates; four lower internal energies advance from their independent
rates; fixed-pressure top storage uses the exact endpoint-minus-previous
saturation-manifold value. The live system remains `46 x 46`. One `1.0 s`
step is compared with two sequential `0.5 s` steps at the same `t=1 s`
endpoint using one fixed colored trust-region solver. Initial-rate consistency,
grid refinement, endpoint rank/condition/spectrum/registry, exact discrete
kinematics, conservation, physicality, provider, call, and wall gates are
frozen. Preparation performs no property evaluation, solve, or timestep. One
execution is authorized only after commit.

2026-07-27 Core V3 initializer first-step refinement result: DD-115 executes
once from frozen commit `28ba8d9` and fails the precommitted dynamic-handoff
gate. All three `46 x 46` backward-Euler roots converge below `2.74e-13`, all
endpoint Jacobians retain rank `46/46`, and physicality, ordered pressure,
exact component/energy kinematics, conservation, provider ownership, runtime,
and call-count gates pass. Coarse/refined inventory, stored energy, pressure,
temperature, and liquid-flow agreement also pass. Algebraic separation is
`3.20e-3` and normalized vapor-flow separation is `2.08e-3`, both above their
`1e-3` limits. Half-step component and energy rates differ from DD-114's
zero-time rates by `2.39e-2` and `1.74e-2`, led by the generic
stripping-to-feed vapor link and bottom-volume rates. This is a localized,
finite transient rather than rank, conservation, or provider failure, and it
is orders of magnitude smaller than DD-105. Nevertheless, the frozen stop is
binding: this initializer-to-step handoff is retired, no short trajectory is
authorized, and no DD-115 timestep or solver tuning may follow.

2026-07-27 Core V3 initializer handoff term-audit contract: DD-116 adds a
read-only diagnostic ledger around the unchanged Core V3 equations. It freezes
the accepted DD-114 `t=0` state and the DD-115 refined `t=0.5 s` and `t=1.0 s`
states, then permits exactly one live residual/property evaluation per saved
state. Every material and energy rate is independently reconstructed from
signed physical inflow, outflow, feed, product, and duty terms. The audit
requires exact rate reconciliation, saved-state reproduction, unchanged term
ownership, direct DWSIM PR provenance, fewer than `5000` property calls, and
less than `30 s` wall time. It performs no solve, Jacobian, timestep,
controller, initializer, or trajectory. A pass may authorize only a
property-free structural feasibility audit for an exact zero-rate or bounded
slow-start selection; it cannot revive or relax DD-115.

2026-07-27 Core V3 initializer handoff term-audit result: DD-116 executes once
from frozen commit `f5117ed`. Its physical evidence is clean: all material and
energy term sums reproduce saved rates below `2.74e-13` scaled; pressure,
temperature, hydraulic/vapor/product flows, condenser duty, ownership, and
provider provenance reproduce; and only `85` property calls are used in
`0.162 s`. The initial bend is dominated by a `437.64 lbmol/h` increase in
the energy-owned combined-reboiler/sump-to-stripping vapor link. That term
explains `-307.70 lbmol/h` of the bottom n-butane rate change and
`-0.956 MMBTU/h` of the bottom energy-rate change. The formal aggregate gate
still fails because DD-115 serialized its nominal exponential-step rate
coordinate separately from the effective finite-step component rate; direct
reinterpretation differs by `3.08e-5` scaled even though the physical rate
reconciles. DD-116 is not rerun or changed. Its raw stop remains binding unless
an explicitly authorized, static, zero-call adjudication accepts that
representation-only distinction.

2026-07-27 Core V3 DD-116 representation-gate adjudication contract: DD-117
is a static governance exception authorized by the user. It freezes the
immutable DD-115/DD-116 evidence, permits replacement of only the failed
`physical_reproduction` gate, and preserves every other result and gate. The
replacement keeps all actual pressure, temperature, flow, product, and duty
checks, then algebraically reconstructs DD-115's exponential endpoint
inventory, effective finite-step rate, and reported nominal/effective rate
mismatch. No property, residual, Jacobian, solver, initializer, timestep,
controller, or trajectory call is permitted. Passing may authorize only a
property-free structural zero-rate feasibility audit.

2026-07-27 Core V3 DD-116 representation-gate adjudication result: DD-117
passes once from frozen commit `faf7850`. Every inherited non-reproduction
gate remains unchanged and true. Actual physical-field reproduction,
exponential endpoint inventory reconstruction, effective finite-step rate
reconstruction, and nominal/effective mismatch reconstruction all have exactly
zero error. No numerical evidence changes and no property, residual, Jacobian,
solver, initializer, timestep, controller, or trajectory call occurs. DD-116's
term-level conclusion is accepted: the startup rate bend is physical and
balance-explained, not an equation-ownership discontinuity. One property-free
structural zero-rate feasibility audit is authorized.

2026-07-27 Core V3 zero-rate feasibility result: DD-118 passes property-free.
For three components, removing the 19 rate unknowns by fixing them exactly to
zero leaves the live DAE core `46 x 46`, structural rank `46`. Retaining all
six DD-112 selection targets produces `52 x 46`, rank `46`; equivalently,
adding 19 zero-rate rows to the original initializer gives `71 x 65`, rank
`65`. Maximum matching leaves exactly the three global component inventories,
one global stored-energy target, and two terminal total holdups unmatched. The
two-component audit reproduces the generic `Nc+3` surplus. The next numerical
architecture must treat the `Nc+1` inherited global component/energy totals as
diagnostics rather than exact steady-state constraints. Drum and sump total
holdups remain provisional terminal scale selections, subject to a frozen live
rank and compatibility audit. No root solve, initializer execution, or
dynamics is authorized by this structural pass.

2026-07-27 Core V3 live zero-rate readiness contract: DD-119 is frozen but
not yet executed. The 19 conserved rates are fixed exactly to zero and removed
from the numerical unknown vector. The remaining 46 coordinates contain 19
conserved-state and 27 algebraic coordinates. The residual retains all 46
unchanged DAE/storage/pressure rows and adds the two terminal total-holdup scale
selections; whole-column component and stored-energy targets are diagnostics.
Two independent saved states, two colored Jacobian steps, and one full
canonical cross-check are required. No nonlinear root solve, timestep,
controller, retry, or dynamics is part of DD-119.

2026-07-27 Core V3 live zero-rate readiness result: DD-119 passes once from
contract commit `a56d2ce`. At both frozen states, the DAE-only matrix is
formally rank `46/46` but has condition `2.54e13` to `3.76e13`. The two
terminal holdup rows regularize those near-scale directions: the augmented
`48 x 46` matrices remain rank 46 with condition below `5.68e3`. Both
finite-difference steps are spectrum-stable, the canonical colored/full
difference is zero, conservation is at roundoff, and all `7113` DWSIM calls
pass in `3.144 s`. The starting residual remains about `0.06`; no root has
been found. One frozen overdetermined zero-rate root campaign is authorized to
test whether the terminal targets are exactly compatible with the DAE root.

2026-07-27 Core V3 zero-rate root contract: DD-120 is frozen but not yet
executed. Exactly the two DD-119 states feed one bounded 20-color
`least_squares(method="trf")` campaign on the unchanged `48 x 46` residual.
Every DAE and terminal row must close below `1e-8`, both starts must reach the
same interior physical endpoint, and the endpoint Jacobians must pass the
frozen rank, condition, spectrum, coloring, conservation, provider, call, and
wall gates. A failure retires this terminal-scaled path without variation. No
timestep, controller, continuation, or dynamics is part of DD-120.

2026-07-27 Core V3 zero-rate root result: DD-120 fails once from contract
commit `67b9c51`. Both starts converge to the same stationary physical endpoint
within `1.36e-9`. The terminal rows close below `7.04e-12`, and all gates pass
except exact residual closure. The DAE rows stop at `2.4486e-3`, with
left-null residual projection `7.6737e-3`. Thus the inherited drum and sump
holdups are not exactly compatible with the zero-rate DAE root under the
frozen operating specifications. The terminal-scaled path is retired without
retry, target adjustment, alternate solver, continuation, timestep, or
dynamics. Any DAE-only successor must be separately justified rather than
treated as the next automatic solver variation.

2026-07-27 Core V3 terminal gauge result: DD-121 passes once from contract
commit `aa4ed13`. Homogeneous `+/-1%` scaling of reflux-drum inventory leaves
all 46 DAE rows exactly unchanged. Homogeneous scaling of combined
reboiler/sump inventory and internal energy changes the DAE vector by at most
`6.00e-14`. In both cases composition and bottom specific internal energy are
unchanged, while only the applicable terminal target row moves by exactly
`+/-0.01`. The six residual evaluations use `169` accepted DWSIM calls in
`0.960 s`; no Jacobian or solve occurs. Terminal amounts are therefore gauge
selections, not independent steady operating specifications. The next
authorized design is one frozen square `48 x 48` zero-rate system that keeps
the drum and sump amount targets and releases positive distillate and bottoms
rates as level-controller outputs. DD-120's broader claim of target
incompatibility is narrowed accordingly.

2026-07-27 Core V3 controlled-terminal zero-rate result: DD-122 passes once
from contract commit `76404ac`. Adding only positive transformed distillate
and bottoms rates to the unchanged 46-row DAE plus two terminal amount rows
gives a structurally full-rank `48 x 48` system. Two independent starts reach
the same root within `8.74e-12`; final residuals are below `1.38e-13`, endpoint
rank is `48/48`, condition is about `5.94e3`, and every frozen physical,
conservation, provider, bound, and efficiency gate passes. The stationary
level-control outputs are `D=2255.740878` and `B=4887.233122 lbmol/h`; their
sum matches the feed. This is an accepted zero-rate initial condition, not yet
a dynamic trajectory. The next contract must define bumpless terminal
level-control ownership initialized at these outputs. Imported product rates
remain comparison targets unless a separate operating degree of freedom is
introduced to own throughput.

2026-07-27 Core V3 controlled-terminal dynamic structure: DD-123 adds explicit
geometry-based level ownership without changing the accepted DD-122 column
physics. Two PI-memory states and rates plus positive distillate and bottoms
outputs add four equations to the inherited ledger, producing a square,
structurally full-rank `50 x 50` C3/C4 system and a `40 x 40` generic
two-component system. Liquid volume is total inventory divided by live DWSIM
liquid molar density. The reflux drum uses a horizontal cylinder with two
hemispherical heads; the sump uses a vertical cylinder. Controller memories
are initialized from `D=2255.740878` and `B=4887.233122 lbmol/h`, so the
stationary handoff has no artificial output jump. This pass is property-free
and authorizes only a separately frozen live zero-time level reconstruction
and leading-system audit before any timestep or trajectory.

2026-07-27 controlled-terminal live handoff status: DD-124 and DD-125 do not
alter the accepted architecture or supply a physical result. DD-124 aborts on
a mismatched pressure-specification keyword before its first governed
residual. The separately frozen keyword-only DD-125 correction then aborts
because setpoint reconstruction labels the call as `preparation`, while the
provider-governed residual accepts only `residual` or `jacobian`. Neither run
returns a controlled-terminal residual, reconstructs a level, evaluates a
Jacobian, solves a nonlinear system, or takes a timestep. Per the DD-125 hard
stop, another automatic corrective successor is prohibited. DD-122 remains
the accepted stationary zero-rate state; DD-123 remains structural only; the
live controlled dynamic handoff is unproven.

2026-08-05 controlled-terminal interface qualification: after explicit user
authorization to reopen the interface-only stop, DD-126 replaces the invalid
setpoint call label with the provider-supported `residual` label. The live
50-row controlled DAE closes at `3.09e-11`; all four controller rows are
exactly zero. Direct DWSIM density plus frozen geometry gives a reflux-drum
level of `0.469288` diameter fraction and sump level of `0.524957` height
fraction. The accepted stationary outputs reproduce exactly at
`D=2255.740878` and `B=4887.233122 lbmol/h`. All 57 provider calls pass. This
is a development interface preflight, not a Jacobian or timestep result. It
authorizes one separately frozen live `50 x 50` Jacobian audit.

2026-08-05 controlled-terminal numerical leading system: DD-127 executes once
from frozen contract commit `ce7c1be` and passes every gate. The stationary
50-row residual remains `3.09e-11`, all four controller rows and repeated-call
differences are zero, and both central-difference Jacobians have rank `50/50`.
The worst condition is `2.498329e6`, spectrum change is `9.46e-5`, and the
graph-colored matrix matches the full canonical matrix exactly. Geometry-based
levels, stationary product outputs, pressure, conservation, and direct DWSIM
ownership all pass. This proves the live controlled-terminal leading system is
numerically usable at the accepted root. It does not prove a timestep or
trajectory; one separately frozen implicit root-hold step is the only
authorized successor.

2026-08-05 controlled-terminal stationary first step: DD-128 passes the first
actual time-discretization gate. One `1.0 s` backward-Euler root and two
successive `0.5 s` roots close below `6.90e-13`; both endpoint Jacobians retain
rank `50/50` with worst condition `2.084358e5`. The accepted state remains
stationary to machine scale: inventory motion is `2.55e-12` relative,
product-rate drift is `2.25e-13`, and the largest coarse/refined discrepancy is
`2.82e-11`. The 15 component inventories, four lower energies, derived top
energy, and two PI memories all satisfy their discrete kinematics. This is the
first evidence that the controlled Core V3 DAE can preserve its accepted
steady state without an artificial startup transient. It authorizes one
separately frozen moving-step test, not a trajectory.

2026-08-05 controlled-terminal moving-step status: DD-129 does not produce a
scientific result. Its three frozen solve paths reach final result assembly,
where JSON serialization rejects a NumPy boolean in the controller-direction
gate. The numerical metrics are not retained, so no claim is made about moving
step convergence, refinement, direction, or rank. This is a reporting-interface
abort rather than a model failure. DD-128 remains the accepted stationary
first-step boundary. No retry or trajectory is authorized without an explicit,
separately frozen JSON-coercion-only successor.

2026-08-05 controlled-terminal first motion: DD-130 successfully preserves the
exact DD-129 scientific contract while correcting only JSON boolean reporting.
The physical result is coherent: `D` falls by `0.02365%`, `B` falls by
`0.41957%`, controller memory rates are negative, and the drum/sump accumulate
`0.735/20.309 lbmol/h` after both level setpoints rise by `0.1%`. All three
implicit roots close below `4.85e-13`; refined endpoints pass; both Jacobians
retain rank `50/50` and condition near `2.09e5`; all physical and conservation
gates pass. The campaign nevertheless fails its frozen efficiency gate at
24,165 versus fewer than 16,000 DWSIM calls. The ledger shows 23,520 calls are
from 19 colored Jacobian rebuilds, while every full residual needs only 28
calls. Controlled trajectories remain stopped. Future work should design and
freeze Jacobian reuse or modified Newton behavior rather than alter physics,
controller tuning, provider packets, or the accepted moving response.

2026-08-05 controlled-terminal solver-efficiency architecture: DD-131 replaces
the repeated-Jacobian trust-region pattern prospectively, without rerunning the
column. The modified-Newton kernel builds and LU-factorizes one 21-color
Jacobian per root, then uses residual-only corrections with fixed backtracking.
It rejects bound violations without evaluating, clipping, or projecting them;
there is no rebuild or fallback. The controlled structure remains rank `50/50`
for three components and `40/40` for two. Using DD-130's measured 28 calls per
residual, the absolute worst-case three-root budget is 7,673 calls, below the
8,000 gate. DD-131 makes zero live provider or column calls. This authorizes
one frozen live efficiency proof that must reproduce DD-130's saved physical
endpoints; it does not authorize a trajectory.

2026-08-05 controlled-terminal modified-Newton live result: DD-132 demonstrates
the intended computational improvement. Each of the three moving roots uses
one 21-color Jacobian, one LU factorization, and two residual-only corrections;
all roots close below `1.77e-9`. Provider calls fall from 24,165 to 3,809
(`84.2%`) and wall time to `2.281 s`. Every physical, controller-direction,
refinement, kinematic, pressure, conservation, and provider gate passes. The
formal campaign fails only because the half2 transformed bottom-to-stripping
vapor-flow coordinate differs from DD-130 by `1.017993e-7`, versus the frozen
`<1e-7` limit. The associated physical endpoints pass and the next coordinate
difference is below the limit. Preserve the no-retry stop. A static physical-
equivalence adjudication may be considered only under separate authorization;
no controlled trajectory is authorized.

2026-08-05 controlled-terminal physical-equivalence result: DD-133 statically
decodes the immutable DD-130 and DD-132 coarse, half1, and half2 endpoints into
actual inventories, compositions, rates, temperatures, hydraulic and vapor
flows, pressure, condenser duty, controller states, levels, and products. All
57 physical comparisons pass. The disputed half2 bottom-to-stripping vapor
flow differs by `1.017993196e-7` relative, below the frozen `<2e-7` physical
limit. The adjudication uses zero provider or model evaluations and preserves
both source classifications. This validates the one-Jacobian modified-Newton
endpoint as physically equivalent and authorizes only a separately frozen
short controlled-trajectory contract; no trajectory has occurred.

2026-08-05 controlled-terminal short-trajectory contract: DD-134 freezes the
first bounded trajectory after DD-133. It retains the exact DD-132 physical
state and dual-level disturbance and compares `10 x 1.0 s` against
`20 x 0.5 s` over 10 seconds. Every root uses the one-Jacobian modified-Newton
kernel; every step is gated for closure, rank, conditioning, physicality,
pressure order, conservation, exact discrete kinematics, and commanded
controller direction. First-step reproduction and coarse/refined endpoint
agreement are explicit gates. The absolute provider ceiling is 80,000 calls.
The contract is frozen but unexecuted; execution requires separate user
authorization.

2026-08-05 controlled-terminal short-trajectory result: DD-134 demonstrates
that the one-frozen-Jacobian rule is efficient but not robust over repeated
steps. The coarse path fails its seventh root at `t=7 s` with residual
`5.091822e-8`; the refined path fails its sixth root at `t=3 s` with residual
`1.579973e-8`. In both cases, the fixed-fraction line search cannot accept a
further correction. All completed states remain physical, conservative,
pressure ordered, correctly directed, full rank, and well inside the call and
wall limits. Coarse/refined states at the shared `t=3 s` point agree within the
frozen trajectory tolerances. Therefore DD-134 identifies numerical
globalization loss near the residual floor, not model or grid divergence. The
one-frozen-Jacobian controlled-trajectory path is stopped without retry.

## Seven-Volume Core V3 Dynamic Boundary

DD-170 generalizes the conserved Core V3 dynamic DAE ledger from the default
five-volume topology to the accepted DD-169 seven-volume topology. Component
inventories are the only differential states. Temperatures, phase
compositions, five Francis liquid flows, six energy-owned vapor flows, and
condenser duty are algebraic. Internal energy is derived from inventory and
temperature through provider-consistent properties rather than introduced as
an independent state.

For three components, the resulting dynamic solve ledger is `54 x 54` and has
full structural rank. Its adjacency dependencies are generated from topology
links, so interior volume count can change without named-stage equation code.
The accepted DD-169 product rates remain fixed open-loop inputs for this first
contract. DD-170 is structural only: a live leading-Jacobian and consistent-
derivative audit is the next gate, and dynamic integration is not yet
authorized.

DD-171 completes that live numerical gate at the accepted DD-169 root. The
zero-rate residual closes at `4.98e-13`, the provider-consistent storage
gradient is stable to step halving, and both complete `54 x 54` leading
matrices retain rank `54` with condition about `50.97`. No registered coupling
is missing or exceeded, and component and energy conservation remain at
machine scale. Exact-state memoization serves approximately `79.1%` of logical
property requests, yielding an `8.446 s` audit wall without changing property
ownership.

The seven-volume architecture is therefore ready for one stationary implicit
root-hold step. This authorizes neither a disturbance nor a trajectory: the
first timestep must prove that backward Euler preserves the accepted root and
that one full step agrees with two half steps before moving dynamics begin.

DD-172 supplies that proof. One `1.0 s` backward-Euler root and two successive
`0.5 s` roots all close below `3.82e-13`, retain rank `54`, remain physical and
conservative, and move component inventory by no more than `1.04e-12`
relative. The full and refined endpoints agree at `1.03e-14` relative
inventory. Topology-generated colored Jacobians plus exact-state memoization
complete all three roots in `4.447 s` with `7,344` logical property calls.

The architecture is now authorized for one small open-loop moving-step proof.
That next gate must introduce one predeclared physical input change and verify
direction, refinement, rank, conservation, and physicality before any
multi-step trajectory or controller is considered.

DD-173 performs that first moving gate with a `+0.1%` feed-rate and feed-
enthalpy step. Every nonlinear, rank, physical, conservation, direction, and
global-response check passes. Both discretizations accumulate
`0.00198415944 lbmol` over one second and agree in total inventory within
`5.75e-13 lbmol`. The formal campaign nevertheless stops because one local
component's full/refined relative inventory difference is `1.522960e-6`, above
the frozen `1e-7` limit; the corresponding absolute difference is only
`5.9660e-6 lbmol`.

This is a refinement-metric failure, not evidence of a divergent or
nonconservative response. It does not authorize a trajectory. The only
defensible successor is a zero-call physical-scale adjudication of the saved
endpoints before deciding whether a separately frozen smaller-timestep moving
proof is warranted.

DD-174 performs that immutable-endpoint adjudication with zero model,
provider, solver, or endpoint-regeneration calls. Maximum full/refined
component difference is `3.275352e-5 lbmol`; the L1 difference is
`1.164692e-4 lbmol`; the maximum difference relative to its volume's initial
holdup is `7.203869e-7`; and the signed column-total difference is
`-5.746514e-13 lbmol`. Every frozen physical-scale and inherited conservation
gate passes.

DD-173 remains formally failed, and no trajectory is authorized. The
architecture is authorized only for one separately frozen moving proof using
the unchanged disturbance and solver at a smaller grid: one `0.25 s` step
versus two successive `0.125 s` steps.

DD-175 executes that smaller-grid proof. All three roots remain full-rank,
physical, conservative, and tightly closed. Every DD-174 physical-scale gate
passes, and the strict relative-inventory discrepancy falls by `12.99x`, from
`1.522960e-6` to `1.172326e-7`. The remaining absolute component difference
is only `2.535865e-6 lbmol`, while total accumulation agrees within
`8.13e-14 lbmol`.

The retained `<1e-7` relative-inventory gate nevertheless misses by `17.2%`.
Because the DD-175 contract made any failed gate a hard stop, this moving-step
campaign ends without a trajectory or another tuned grid. The numerical
evidence supports timestep convergence; the stop reflects the precommitted
authorization rule, not rank loss, conservation failure, or dynamic blowup.

DD-176 corrects the prospective accuracy policy without changing either
historical result. New Core V3 moving-step and trajectory contracts use a
topology-neutral physical refinement assessment: absolute component,
`1 lbmol`-floor-relative, volume-holdup-relative, L1, and signed-total
inventory differences. The old unfloored component-relative maximum remains
reported as a diagnostic but is no longer a standalone campaign veto.

All equation, nonlinear, equilibrium, physicality, kinematic, conservation,
response, rate/algebraic refinement, provider, and performance gates remain
in force. Under this prospective policy, the immutable DD-175 evidence is
sufficient to draft one separately frozen short open-loop trajectory using
the `0.25 s` and `0.125 s` grids. No trajectory or controller is authorized
until that new contract is committed.

DD-177 supplies the first accepted seven-volume moving trajectory under that
policy. The `8 x 0.25 s` and `16 x 0.125 s` paths both complete the two-second
horizon. All 24 roots retain rank `54`, close below `4.15e-12`, remain
physical and conservative, and use DWSIM PR without fallback. Positive total
accumulation is `0.003968318883 lbmol` on both grids.

Every shared-time comparison passes. Worst absolute component and
volume-holdup-relative differences are `1.558675e-5 lbmol` and
`3.428178e-7`; rate and algebraic differences remain near `1.2e-6`. The old
unfloored diagnostic reaches `7.258663e-7`, demonstrating that it would have
rejected a coherent trajectory for the same trace-component scaling reason.
One separately frozen modest open-loop extension is now authorized.
Controllers remain outside the seven-volume dynamic boundary.

DD-178 executes that extension over ten seconds. All 120 moving roots and all
40 shared-time comparisons pass their numerical, physical, conservation, and
provider gates. Worst residual is `4.740065e-12`; rank remains `54`; worst
condition is `1.434602e7`; and both grids accumulate the expected
`0.019841594413 lbmol` within approximately `1e-12 lbmol`.

The campaign nevertheless fails formally because it inherited DD-175's
absolute `<0.01 lbmol` maximum-response gate, which was intended for a
subsecond interval and is incompatible with the known ten-second integrated
feed increment. This is a contract-scaling defect. DD-178 remains failed and
cannot be rerun. Only a separately frozen zero-call response adjudication may
use the immutable evidence to establish a duration-scaled policy before any
future trajectory is considered.

DD-179 performs that zero-call adjudication. Coarse and refined accumulation
match their path-integrated expected external flow within `6.7445e-11` and
`1.7977e-11` relative, differ from each other by only
`9.8155e-13 lbmol`, and preserve every non-response DD-178 gate. DD-178's
formal failure remains unchanged.

Future trajectory response acceptance is duration-scaled: actual inventory
accumulation must match integrated expected external flow rather than remain
below a fixed absolute ceiling inherited from a shorter run. One separately
frozen longer open-loop trajectory is now authorized under the DD-176 and
DD-179 policies. Controllers remain outside the current boundary.

DD-180 completes that longer proof over thirty seconds. Both `0.25 s` and
`0.125 s` paths complete all 360 roots with full rank, tight residual closure,
physical states, exact kinematics, conservation, and DWSIM PR ownership. All
120 same-time comparisons pass. Actual accumulation is
`0.059524783239 lbmol` on each grid and matches integrated external flow at
approximately `1e-11` relative.

The largest physical refinement differences occur at intermediate times,
with `5.143323e-5 lbmol` maximum absolute and `1.658663e-4 lbmol` L1 error;
both remain inside their frozen limits and do not grow monotonically to the
endpoint. Open-loop validation is therefore complete for this stage. The
next boundary is structural terminal-inventory-control design only. A live
controller, controller tuning, and controlled trajectory remain unauthorized.

DD-181 isolates the principal seven-volume runtime cost without changing this
scientific boundary. The `54 x 54` implicit Jacobian has 17 structural colors,
so each central-difference matrix consists of 34 independent complete residual
evaluations. DD-180 executed those evaluations serially. Process-isolated
DWSIM workers reproduce the same matrix, rank, condition, singular spectrum,
and delegated property count while reducing median matrix time from
`0.271654 s` with one worker to `0.102903 s` with four workers (`2.640x`).

The production architecture may therefore use one persistent four-process
DWSIM pool to construct colored Jacobians. Workers must own independent DWSIM
provider instances and exact-state caches; matrix assembly remains
deterministic in the main process. Pool creation is not a per-Jacobian
operation because four-worker startup is about `5.714 s`. Integration into the
step solver requires a separate equivalence proof before any controlled or
longer trajectory.

DD-182 integrates that worker model into one real `least_squares(method="trf")`
backward-Euler root. The main process continues to own every ordinary residual,
trust-region decision, convergence test, and endpoint evaluation. An optional
Jacobian-builder hook delegates only the 34 colored perturbation residuals;
the default path remains serial. The serial and parallel roots each require
four Jacobians and are identical in matrices, solver decisions, and endpoint.
Parallel solve wall falls from `1.252650 s` to `0.534514 s` (`2.344x`).

The next performance boundary is a short multi-root proof with one pool kept
alive for the entire run. This must demonstrate exact serial equivalence and
amortize the approximately `5 s` startup before the parallel path becomes the
production default. Controller logic remains outside that proof.

DD-183 completes the multi-root production qualification. One serial and one
persistent-parallel path each advance the same disturbed seven-volume model
through 16 successive `0.25 s` roots. Each worker refreshes the new root's
inventory, provider-derived storage, component-rate scales, and physical-state
template once before that root's first Jacobian. Later Jacobians reuse only
that current-root basis. All 56 paired matrices, SciPy decisions, and accepted
states are exactly identical.

The persistent four-worker path is therefore the authorized production
Jacobian architecture for Core V3. The pool is created once per simulation,
workers retain independent DWSIM providers and exact-state caches, evolving
root data is supplied explicitly, and deterministic matrix assembly remains in
the main process. The four-second trajectory improves from `23.359 s` serial
to `12.480 s` parallel, or `1.627x` faster after charging startup. The serial
builder remains the reference and fallback for development diagnostics, not an
automatic runtime fallback after a parallel failure.

DD-184 adds the first seven-volume terminal inventory-control ownership layer.
Distillate and bottoms cease to be fixed open-loop parameters and become
positive log-ratio algebraic outputs of two geometry-based PI level
controllers. Each controller adds one integral-memory state, one memory-rate
variable, and two equations. The resulting ledger has 23 states, 23 derivative
variables, 35 algebraic variables, and 58 equations; its `58 x 58` incidence
matrix has full structural rank.

Controller ownership is terminal-only. The top output enters the reflux-drum
component and energy balances, the bottom output enters the combined
reboiler/sump balances, and both product component draws use live terminal
liquid composition. Interior equations and topology-generated links are
unchanged. DD-184 is structural evidence only: the inherited geometry and PI
constants are not yet tuned, and live residual, Jacobian, timestep, and
controlled-trajectory work remain separately gated.

DD-185 validates that controller ownership numerically at the accepted DD-169
root. Live DWSIM liquid densities map the terminal inventories to a `0.459899`
top level fraction and `0.427453` bottom level fraction. Taking those exact
values as setpoints and initializing both integral memories and product log
ratios at zero gives a bumpless handoff: distillate remains `2220.952340` and
bottoms remains `4922.021660 lbmol/h`, with exactly zero controller residual.

The complete zero-time residual remains `4.979842e-13`. Both finite-difference
`58 x 58` leading Jacobians have rank `58`, no unexpected couplings, worst
condition `1.432411e3`, and spectrum change `8.604470e-11`. DD-185 therefore
authorizes one separately frozen controlled stationary root-hold implicit-step
contract. It does not qualify controller tuning or authorize a disturbed
controlled trajectory.

DD-186 performs the first controller-enabled implicit timestep while holding
the DD-169 operating specification unchanged. One `1.0 s` backward-Euler root
and two successive `0.5 s` roots all close below `3.82e-13` with rank `58`.
Worst condition is `8.973645e5`, comparable to the accepted open-loop
stationary-step conditioning.

The stationary handoff remains effectively exact. Maximum controller-memory
motion is `3.496572e-17`, maximum product-rate motion is `8.499913e-15`
relative, and maximum level error is below `1e-15`. Full and refined endpoint
inventories agree within `1.282663e-14` relative. This authorizes one
separately frozen small controlled moving-step contract. Controller tuning and
controlled trajectories remain unauthorized.

DD-187 applies the first controller-enabled disturbance: feed component rates
and feed enthalpy increase together by `0.1%`, preserving feed composition and
specific enthalpy. Product log ratios are always referenced to the fixed
DD-169 product rates; they are not compounded from a prior endpoint. One
`0.25 s` root and two successive `0.125 s` roots all close below `1.63e-12`
and retain rank `58`, with worst condition `1.434585e7`.

Both grids accumulate `4.960398e-4 lbmol` over the quarter-second horizon and
agree within every physical-scale inventory, rate, algebraic, controller,
product, and level refinement limit. This is the first accepted moving result
for the seven-volume terminal-control layer. It authorizes one separately
frozen short controlled trajectory, but the extremely small product response
at this horizon does not qualify the inherited PI constants as tuned.

DD-188 chains that controller-enabled formulation for two seconds on
`8 x 0.25 s` and `16 x 0.125 s` grids. All 24 roots remain physical,
conservative, rank `58`, and closed below `3.42e-12`. Both paths have positive
monotone accumulation and reproduce their separately integrated external
flows to about `8e-11` relative. Controller-memory, product-rate, terminal-level,
rate, algebraic, and all physical inventory refinement metrics except signed
total remain inside their frozen limits at every shared time.

DD-188 is nevertheless formally failed. Evolving controller outputs make the
two first-order grids integrate slightly different external product flow; the
resulting total-inventory difference reaches `5.928153e-9 lbmol`, above the
frozen `<1e-9 lbmol` cross-grid and signed-total limit. The trajectory cannot
be rerun or reclassified. No longer live controlled trajectory is authorized
unless a separately frozen zero-call adjudication establishes a prospective
response-scaled total-difference policy.

DD-189 performs that adjudication without a model, provider, solver, or
endpoint-regeneration call. DD-188's actual coarse-minus-refined total
difference is `-5.928153e-9 lbmol`; the difference between the two paths'
independently integrated external flows is `-5.928164e-9 lbmol`. The
unexplained remainder is only `1.051936e-14 lbmol`, and the grid difference is
`1.493874e-6` of the accumulated response.

The architecture therefore retains the physical inventory policy but refines
its interpretation for controlled trajectories. When external product outputs
evolve, signed total is a required diagnostic rather than an absolute veto;
the grid difference must instead match the independently integrated external
flow difference within `1e-10 lbmol` and remain below `1e-5` of response. All
absolute-component, floor-relative, volume-relative, L1, controller, closure,
and conservation gates remain mandatory. DD-188 stays formally failed, while
one separately frozen modest controlled trajectory is authorized under the
prospective policy.

DD-190 extends the unchanged controlled disturbance to ten seconds on
`40 x 0.25 s` and `80 x 0.125 s` grids. All 120 roots remain physical,
conservative, rank `58`, and closed below `3.96e-12`. Both paths are positive
and monotone, and each matches its integrated external flow within
`1.55e-11` relative. The unexplained coarse/refined total difference stays
below `7.98e-13 lbmol`, confirming that no mass leak appears.

The campaign nevertheless fails its precommitted timestep-refinement gates.
The total-grid difference relative to accumulated response exceeds `1e-5` at
`4.75 s` and reaches `5.313564e-5` at `10 s`. Terminal-level refinement
exceeds `1e-8` at `7.25 s` and reaches `1.754111e-8`. All other physical,
rate, algebraic, PI-memory, and product refinements pass. DD-190 therefore
stops the current controlled-trajectory extension on numerical accuracy, not
model instability. A new explicit integration decision is required before a
smaller-grid proof, parallel controller integration, tuning, or longer run.

DD-191 qualifies the persistent four-worker Jacobian architecture against the
controlled `58 x 58` root itself. The serial and parallel solves use the same
17-color central-difference pattern, controlled residual, state, scales,
provider, and trust-region settings. All four paired Jacobians, SciPy
decisions, and endpoint quantities are bit-for-bit identical. Both roots close
at `1.621788e-12`, retain rank `58`, and have condition `1.434585e7`.
Parallel solve wall falls from `2.071781 s` to `1.086940 s`, a `1.906x`
speedup excluding the separately measured worker startup.

DD-191 formally fails only its startup-ping participation check. A process
pool is not required to schedule four trivial ping tasks on four different
processes, so that preflight observed three IDs. The actual evidence is
stronger: every 34-task Jacobian used the same four worker IDs. DD-192
adjudicates that reporting defect from immutable artifacts with zero live
calls and authorizes persistent parallel Jacobians for controlled steps.

This authorization changes computation ownership, not model equations or
acceptance standards. The main process still owns ordinary residuals, solver
decisions, endpoint evaluation, and deterministic matrix assembly. Isolated
workers evaluate only colored perturbation residuals through DWSIM. DD-190's
grid-accuracy failure remains unresolved; the next live campaign must be a
separately frozen finer-grid refinement proof, with no controller tuning or
longer-horizon extension bundled into it.

DD-193 attempts the authorized finer-grid controlled proof on `80 x 0.125 s`
and `160 x 0.0625 s` paths. It is stopped after at least `1503 s`, over six
times its frozen total-wall limit, before a complete result or endpoint is
written. The original parent and four workers remain CPU-bound until the
operator stop; no scientific trajectory gate is therefore classified.

The scaling failure is in audit instrumentation rather than the DAE equations.
Every perturbation task calls `ProviderCallAudit.report()`, which scans the
entire accumulated record list for violations and rebuilds grouped counts.
Across a long persistent-worker campaign, repeated full-ledger reporting adds
superlinear bookkeeping. A successor must replace task-level full reports with
incremental ownership evidence and enforce its wall deadline while executing.
DD-193 cannot be retried, and DD-190's timestep-accuracy question remains open.

The DD-194 correction gives `ProviderCallAudit` a constant-time `record_count`
and a `report_since(start_index)` operation that validates only the current
task's appended records. On a 200,000-record development ledger, checking the
newest 51 records takes about `56.5 microseconds` versus `0.278 s` for a full
report. Controlled trajectories also accept an absolute monotonic deadline and
return `stop_reason="deadline"` before starting another root.

The live two-second qualification confirms that the runaway bookkeeping is
gone. All 48 finer-grid roots and every scientific gate pass, including
response-relative total refinement `5.8920e-7` and level refinement
`2.5612e-10`. However, the four-worker trajectory takes `52.396 s` against a
`55.487 s` projected serial baseline, only `1.059x` faster. DD-194 therefore
fails its precommitted meaningful-speed gate and does not authorize the full
ten-second finer-grid campaign.

This closes the brute-force refinement direction. The equations remain
healthy over the qualified short horizon, but first-order backward Euler needs
too many expensive Jacobians to demonstrate ten-second controller accuracy by
repeated timestep halving. The next architecture decision should be a
property-free structural design for a higher-order implicit formula, with no
live trajectory until its state/history ownership and startup procedure are
explicitly gated.

DD-195 defines that higher-order structure as constant-step BDF2. It changes
the time discretization but not physical equation ownership: the controlled
solve remains `58 x 58`, full structural rank, with the same topology-generated
Jacobian pattern. History is fixed input rather than another solved state.

For seven volumes and three components, each of two history levels owns 21
component inventories, seven provider-derived internal-energy storages, and
two PI memories, for 60 saved values. Component and energy derivatives use
`(3*y[n+1]-4*y[n]+y[n-1])/(2*dt)`. PI-memory solve coordinates map to the
same BDF2 derivative exactly. Component endpoints retain the positive
exponential map, and the balance receives the exact BDF2 rate implied by the
endpoint.

One accepted existing backward-Euler step creates startup history. The BDF2
contract is constant-step only; changing `dt` requires discarding its history
and taking a new backward-Euler startup step. The generic eight-volume,
four-component ledger is `82 x 82`, rank `82`, with no named interior logic.
This is structural authorization only. A BDF2 residual and property-free
stationary identity audit must pass before any live root is considered.

DD-196 implements that authorized layer. `ControlledBDF2History` stores fixed
current/prior component inventories, provider-derived internal energies, and PI
memories. The endpoint mapper retains positive exponential inventory
coordinates, computes the exact BDF2 rate implied by the mapped endpoint, and
inverts the PI-memory derivative exactly. A mismatched timestep invalidates the
history.

The controlled BDF2 residual reuses the existing terminal-control physical
residual. It substitutes effective BDF2 component-rate coordinates before the
material balances are evaluated, obtains endpoint governing internal energy
from the accepted provider-owned storage definition, and adds its BDF2 storage
rate exactly once to each energy row. Algebraic variables, product ownership,
controller equations, and physical scales remain unchanged.

The property-free stationary assembly is exactly zero with zero provider calls;
linear and quadratic derivative identities, PI inversion, generic topology,
and invalid-history behavior are tested. This implementation pass authorizes
only a separately frozen live stationary residual/Jacobian parity audit. It
does not authorize a nonlinear solve, accepted BDF2 step, or trajectory.

DD-197 supplies the first live thermodynamic check of that implementation. At
the accepted seven-volume controlled stationary state, identical current and
prior histories produce exactly zero inventory, component-rate, energy-rate,
and PI-memory motion. The complete BDF2 residual is `4.979842e-13` and matches
the backward-Euler stationary residual exactly.

Dense central-difference BDF2 Jacobians at `1e-5` and `5e-6`, plus the
backward-Euler reference Jacobian, all retain rank `58`; worst condition is
`3.172742e7`. BDF2 spectrum sensitivity to finite-difference step is
`1.078595e-7`. Its matrix differs from backward Euler by `0.3330511` in the
reported relative norm because the time-derivative coefficients differ. This
is expected method behavior: the stationary root, registered structure,
physical equations, and provider ownership remain unchanged.

The stationary parity pass authorizes only one separately frozen moving BDF2
step. That successor must use an accepted backward-Euler startup history and a
fixed timestep, compare directly with the accepted backward-Euler refinement,
and pass all closure, rank, physicality, conservation, and accuracy gates
before any BDF2 trajectory is considered.

DD-198 performs the first moving solve with that architecture. The accepted
DD-185 stationary state and DD-187 first `0.125 s` backward-Euler endpoint form
the two history levels; one constant-step BDF2 solve advances to `0.25 s` under
the unchanged `+0.1%` feed disturbance. The residual closes at `3.528219e-12`,
the `58 x 58` Jacobian remains full rank with condition `3.172741e7`, and all
BDF2 component, energy, PI-memory, conservation, physicality, equilibrium, and
provider gates pass.

The BDF2 endpoint differs from DD-187's accepted two-half-step endpoint by at
most `8.664731e-7 lbmol` per component state. Against the frozen backward-Euler
Richardson estimate, BDF2 reduces maximum inventory error from
`2.535865e-6` to `1.669391e-6 lbmol`, a ratio of `0.658313`. This is the first
live evidence that the higher-order formula improves moving-state accuracy
rather than merely preserving closure.

The pass authorizes one short, separately frozen BDF2 grid-refinement proof.
Every path must use one accepted backward-Euler startup and constant BDF2 steps;
duration, grids, limits, and economics must be fixed before execution. Longer
integration and controller tuning remain unauthorized.

DD-199 attempts the authorized two-second BDF2 grid refinement but stops before
a complete path. The backward-Euler startup and first BDF2 endpoint complete;
the next history handoff incorrectly reads direct backward-Euler endpoint
fields from a BDF2 evaluation whose accepted inventory, energy, and PI memory
are grouped under `kinematics`. This is a trajectory adapter defect and yields
no scientific result.

The trajectory kernel now uses method-aware accessors for all three accepted
history families, and its regression chains multiple BDF2-shaped endpoints.
DD-199 remains retired. Only a separately numbered successor with unchanged
physics, grids, solver, and limits may repeat the proof.

DD-200 completes the corrected proof. All 24 roots and every scientific gate
except the legacy absolute signed-total subgate pass. BDF2 reduces worst shared
maximum and L1 inventory differences to about `32.5%` of DD-188 backward Euler,
while retaining full rank, physicality, conservation, and bounded execution.
The only failures occur when cross-grid total difference exceeds `1e-9 lbmol`
at the final two shared times; the final difference is explained by distinct
external product-flow histories within `2.51e-12 lbmol` and is only
`4.996e-7` of response.

DD-200 remains formally failed. The already-established DD-189 policy permits
one zero-call adjudication using saved inventories and total external rates at
every shared time. No live rerun or model change is justified.

DD-201 performs that adjudication. It independently reconstructs each path's
total inventory from saved total feed and product rates using one
backward-Euler startup followed by the BDF2 recurrence. Across all eight shared
times, the worst unexplained coarse/refined difference is
`1.364242e-12 lbmol`, and the worst difference is only `4.994035e-7` of
response. The accepted DD-189 policy therefore passes with zero live calls.

DD-200 remains formally failed, but its scientific BDF2 refinement evidence is
accepted prospectively: two-second BDF2 grid error is about one-third of the
same-grid backward-Euler error. One frozen modest BDF2 trajectory is authorized
next; its numerical and performance contract must precede execution.

DD-202 extends that evidence to the ten-second controlled response that stopped
DD-190. Both constant-step paths complete all `40 + 80` roots with one
backward-Euler startup per grid. Every root remains physical, conservative,
full rank, and provider-governed; all 40 shared-time comparisons pass the
response-scaled total policy established by DD-189 and DD-201.

Against DD-190 on the same `0.25 s` and `0.125 s` grids, BDF2 reduces the worst
maximum inventory difference by `81.07%` and the worst L1 difference by
`85.05%`. Worst level refinement falls from DD-190's `1.754111e-8` to
`1.225224e-9`, and worst response-relative total difference is
`5.203283e-6`, below the frozen `1e-5` limit. The old absolute signed-total
diagnostic still trips as the controlled external outputs separate, but the
unexplained remainder is at most `7.275958e-12 lbmol`.

This result selects constant-step BDF2 as the validated controlled integration
method for the current Core V3 milestone. It authorizes one separately frozen
integration extension, not controller tuning, arbitrary timestep changes, or
an unrestricted production trajectory. Any timestep change still invalidates
BDF2 history and requires a new backward-Euler startup.

DD-203 gives that selected method the production trajectory orchestration
contract already used around backward Euler. The BDF2 runner retains its
default one-step backward-Euler startup and constant-step history ownership,
but now accepts explicit startup and BDF2 step solvers. This is the interface used
by qualified serial, memoized, or parallel Jacobian implementations; the
trajectory itself does not own or silently select a performance backend.

A finite monotonic deadline is checked before startup and before each BDF2
root. Incomplete results distinguish deadline expiration from nonlinear root
failure, retain every completed record with its method label, and expose no
endpoint when no root completed. Requested duration and the final completed
outcome use the same reporting shape as the established controlled trajectory
workflow.

The gate is property-free and does not advance the model. Its pass authorizes
one frozen live serial-versus-performance-path equivalence proof. A longer
BDF2 trajectory remains unauthorized until the injected solver reproduces the
serial Jacobians, decisions, and endpoints under live DWSIM evaluation.

DD-204 supplies that live equivalence proof with one backward-Euler startup and
one BDF2 root at `dt=0.125 s`. The serial path evaluates colored Jacobians in
the main process. The performance path keeps SciPy residual calls, decisions,
and endpoint ownership in the main process while one persistent four-worker
DWSIM pool evaluates only the 34 colored central-difference perturbations per
matrix.

The worker basis is method-aware. For the startup root, each worker reconstructs
the current template, previous inventory and PI memory, provider-owned storage,
and rate scales. For the BDF2 root, each worker reconstructs the accepted
two-level component, internal-energy, and PI-memory history plus current rate
scales. Each worker rebuilds this basis once per root, not once per Jacobian.

Seven paired Jacobians and both complete root outcomes are bit-for-bit equal.
Both methods retain rank `58`, with worst residual `1.868842e-12` and worst
condition `3.172741e7`. Warm-pool trajectory wall improves from `9.543881 s`
serial to `7.369045 s` parallel (`1.295x`), and adjusted worker startup is
`2.035537 s`. This authorizes the persistent parallel Jacobian backend for one
separately frozen longer BDF2 trajectory; it does not yet establish
long-horizon speed or production readiness.

## DD-205 persistent-parallel BDF2 replay

DD-205 applies the DD-204 worker path to the accepted DD-202 ten-second
controlled BDF2 milestone without changing the physical or numerical model.
One persistent four-worker pool evaluates all colored Jacobian perturbations
for the 40-root coarse and 80-root refined paths; the main process retains
SciPy ownership and all nonlinear decisions.

The complete live replay is scientifically identical to DD-202 after
serialization and is `2.047x` faster in trajectory wall time. DD-205 remains
formally failed because its in-memory evidence comparator distinguishes tuple
and list representations of diagnostic index coordinates. This is an evidence
layer defect, not a state, equation, solver, provider, or parallel arithmetic
difference. Production adoption awaits one zero-call persisted-artifact
adjudication; the live campaign shall not be rerun.

DD-206 adjudicates the immutable DD-205 and DD-202 JSON artifacts without
loading model or thermodynamic code. Their complete scientific objects are
exactly equal after the common JSON representation is applied. The sole
DD-205 failure is therefore confirmed as an evidence-comparator type artifact.
The persistent four-worker BDF2 path is adopted for production integration.
SciPy and accepted-state ownership remain in the main process; workers remain
limited to colored Jacobian perturbations and rebuild their physical basis
once per root. The DD-203 between-root deadline remains mandatory.

## DD-207 reusable persistent-parallel backend

DD-207 moves the accepted coordination pattern into Core V3 source modules.
The executor remains caller-owned so one pool can span multiple trajectory
paths. The generic coordinator owns color-task construction, deterministic
assembly, and runtime validation of worker participation, root-basis rebuilds,
and provider authority. The terminal-control adapter owns only serialization
of the backward-Euler or BDF2 root basis and injection of the parallel
Jacobian builder into the existing main-process nonlinear solvers.

The trajectory runner now accepts this adapter through `step_solver_backend`.
It remains the owner of startup/BDF2 sequencing, accepted history, failure
stops, and monotonic deadlines. Serial execution remains the default. This
separation keeps process management and thermodynamic worker initialization at
the application boundary while making numerical ownership reusable and
testable.

DD-208 supplies the live boundary proof for this extraction. The reusable
backend reproduces DD-204's startup and first BDF2 root exactly, including
solver metadata, accepted physical states, residuals, rank, and condition. All
seven Jacobians use four workers with the required per-root basis lifecycle and
no provider fallback. Future parallel BDF2 execution shall use the production
coordinator and adapter; campaign-local closure implementations remain only as
immutable historical evidence.

## DD-209 30-second production horizon

DD-209 is the first horizon extension executed entirely through the reusable
production backend. The scientific model remains the DD-202 controlled
seven-volume system: fixed pressure, a `+0.1%` feed-rate and feed-enthalpy
disturbance, top and bottom inventory PI controllers, DWSIM Peng-Robinson
properties, one backward-Euler startup per path, and constant-step BDF2
thereafter. The coarse and refined paths use `0.25 s` and `0.125 s` steps for
the same 30-second interval.

Both paths complete with full rank, bounded condition, physical states, exact
conservation, equilibrium closure, controller closure, and acceptable
cross-grid response. The persistent worker pool preserves main-process solver
and accepted-state ownership while using all four workers for every colored
Jacobian. No equation, property basis, controller, or timestep is adapted
during execution.

This establishes tested numerical coherence through 30 seconds. It does not
establish process settling, long-horizon controller performance, or acceptable
production throughput. Thermodynamic cost remains material: the two paths use
`1,640,840` logical property calls and `250.435 s` governed wall. The architecture
therefore advances only to one separately frozen 60-second validation, with the
same bounded execution discipline.

## DD-210 worker scaling

The production Jacobian coordinator remains independent of worker count. On
the present eight-core host, DD-210 compares four and eight persistent DWSIM
workers using identical startup and BDF2 roots. All Jacobians and accepted root
reports are exactly equal, including solver decisions, while warm trajectory
wall improves by `1.535x`.

Eight workers are therefore the production default on this host. The executor
remains caller-owned, every matrix must demonstrate actual participation by
all configured workers, and every root must rebuild exactly one physical basis
per worker. Worker count is a deployment setting bounded by available physical
cores, not a model equation or scientific parameter. Four workers remain the
qualified fallback where host capacity requires it.

## DD-211 optional BDF2 coordinate predictor

The controlled BDF2 trajectory now exposes a default-off initial-guess policy.
The accepted default starts each BDF2 root from the previous accepted solve
coordinates. The optional linear policy extrapolates the next coordinate guess
from the two latest accepted vectors. Coordinate history is separate from and
advances with the already accepted physical BDF2 history.

This policy belongs to nonlinear orchestration, not the physical model. It
does not alter endpoint equations, conserved states, controller memory,
thermodynamic calls, Jacobian construction, bounds, or acceptance. Production
continues to use the accepted-endpoint default until a frozen live proof shows
that extrapolation reduces Jacobian work without changing physical endpoints.

DD-212 supplies that live proof. On two independent ten-second, eight-worker
paths, linear extrapolation reduces Jacobian count by `19.718%`, logical calls
by `18.988%`, and warm trajectory wall by `21.501%`. Accepted physical science
agrees within `3.046807e-10`, and all roots and provider/worker gates pass.

Production controlled BDF2 recipes therefore select `linear_extrapolation`
explicitly. The Python API default remains `accepted_endpoint` so historical
contracts and callers retain unchanged behavior. The predictor is not a
fallback mechanism: if an extrapolated root fails, the trajectory stops under
the existing root-failure contract.

## DD-213 60-second production boundary

DD-213 combines the accepted eight-worker source backend and explicit linear
coordinate predictor on both production BDF2 grids for 60 simulated seconds.
Both trajectories complete all 720 roots. Full rank, accepted conditioning,
physicality, equilibrium, conservation, controller response, cross-grid
agreement, worker lifecycle, and DWSIM provider ownership all remain intact.
The architecture is therefore scientifically coherent through this 60-second
controlled horizon.

The campaign nevertheless fails its production wall contract by `8.084 s`:
`308.084 s` governed total versus the frozen `<300 s` limit. The trajectory
itself consumes `276.857 s`, while raw worker startup consumes `3.294 s`. The
remaining `27.933 s` occurs after the trajectory timer ends and before the
process-pool context exits, encompassing evidence extraction and worker
shutdown. Response analysis, result construction, and serialization occur
after the governed timer and cannot cause this failure.
The next architecture work may define a reusable production-session lifetime
for the already caller-owned executor so worker teardown is paid once per
session rather than once per trajectory segment. Longer integration and any
equation, solver, grid, controller, or thermodynamic change remain unauthorized.

## DD-214 reusable production-session lifecycle

The parallel controlled-BDF2 backend can now be hosted by
`TerminalInventoryControlBDF2ProductionSession`. This application-lifetime
object constructs one caller-supplied executor and one accepted parallel step
backend, then routes multiple uniquely named trajectories through them before
an explicit final close. Worker startup, each trajectory call, and final
shutdown have separate timing evidence.

This layer owns resources, not physics. It composes the existing persistent
colored Jacobian, method-aware parallel step solvers, and controlled BDF2
trajectory. Equations, DWSIM provider ownership, finite differences, nonlinear
solver, bounds, scales, controls, and accepted-state rules are unchanged.
Unique trajectory names prevent root-epoch collisions in worker basis caches;
even a failed name remains reserved. A closed session cannot be restarted or
expose its dead backend.

Startup pings are warm-up evidence rather than a worker-participation proof.
Operating-system scheduling may assign those tasks to fewer than all workers.
The governing all-worker gate remains attached to every Jacobian matrix, where
the accepted coordinator enforces both participation and exactly-once basis
reconstruction per root.

DD-214 is property-free. A short live proof must establish the lifecycle with
real DWSIM workers before production recipes adopt it. Longer integration is
still outside the authorized boundary.

DD-215 provides the live lifecycle proof. One eight-worker session completes
two independently named controlled BDF2 paths, remains open between them, and
closes once afterward. Every root and scientific gate passes, every Jacobian
uses all eight workers, and all worker-basis epochs are unique and complete.

Session timing is now an explicit four-part contract: startup, active segment
work, final shutdown, and total lifetime. DD-215 measures `3.015 s` startup,
`22.603 s` active trajectories, `8.310 s` shutdown, and `33.929 s` total. The
session architecture amortizes lifecycle cost across continuation segments; it
does not alter or accelerate an individual nonlinear root. Production code and
reports must retain all timing categories, even when a segment-latency gate
excludes final teardown. Complete-session wall remains separately reportable.

The reusable lifecycle is accepted, but DD-213's original formal wall failure
stands. Before another long trajectory, a frozen qualification must state both
the active-segment latency gate and complete-session lifecycle gate. Neither
may be redefined after observing a result.

## DD-216 executable timing policy

Reusable-session performance is governed by
`ProductionSessionTimingLimits` and `assess_production_session_timing`. A
contract identifies every active segment by unique ordered name and gives each
one its own wall limit. Startup, aggregate active work, final shutdown,
complete session lifetime, and unattributed overhead have independent limits.

The assessor requires segment completion, finite nonnegative observations,
exact name/order agreement, equality of summed segments with the session's
active timer, presence of final shutdown and total wall, and a closed timing
identity. Passing active work cannot hide a slow lifecycle, and passing total
wall cannot hide one slow segment.

Applied statically to DD-215, all gates pass. The complete `33.928759 s`
session is explained by `3.015291 s` startup, `22.602660 s` active work,
`8.309981 s` shutdown, and `0.000827 s` unattributed orchestration. This audit
uses no live provider or model call.

Future production qualification may use one already-validated grid rather
than rerunning a convergence pair. It must nevertheless freeze both segment
latency and complete-session limits before execution and report both afterward.

## DD-217 single-grid production segment

The accepted production segment uses one backward-Euler startup followed by
constant-step BDF2 at `0.25 s` for 60 simulated seconds. One reusable
eight-worker session owns all 240 roots and closes only after the segment.
Every accepted science record and integrated response reproduces DD-213's
coarse validation path exactly.

Active segment wall is `116.236862 s`, while startup and shutdown add
`2.731425 s` and `15.024129 s`; complete session wall is `134.004839 s` with
only `0.012423 s` unattributed. The production path therefore advances one
simulated second per `1.9373` active wall seconds on this host. This is the
accepted 60-second operating unit, not an unrestricted trajectory.

Continuous production requires a method-aware continuation state. The current
trajectory entry point always creates a backward-Euler startup from supplied
initial inventory, controller memory, and solve coordinates. Reusing it for a
second segment would interrupt BDF2 history. A continuation payload must own:

- current and prior component inventories;
- current and prior provider-derived internal energies;
- current and prior controller memories;
- current and prior solve coordinates;
- the current physical template;
- constant timestep and elapsed simulation time.

A continuation call must begin directly with BDF2, retain the live session,
advance unique root epochs, and preserve controller and conservation identity.
That structural handoff is required before another live segment.

## DD-218 five-minute dynamic execution

DD-218 runs the accepted seven-volume controlled DAE continuously for 300
simulated seconds using `0.25 s` BDF2 after one startup. All 1,200 roots close,
and the first 60 seconds reproduce DD-217 exactly. Numerical rank,
conditioning, equilibrium, conservation, controller equations, physicality,
DWSIM ownership, worker participation, and timing remain accepted.

The sole formal failure is a response-policy assumption inherited from the
short disturbance proofs: total inventory was required to increase strictly
for the entire horizon. The long run shows the expected controller transition.
Inventory accumulates initially, peaks near `280 s`, and then decreases through
the final four sampled intervals as bottoms withdrawal continues to rise. Exact
external-flow recurrence still explains the inventory trajectory.

This result separates dynamic model health from response classification. The
model does not blow up or lose closure over five minutes. DD-218 nevertheless
retains its formal failed label until a separately frozen zero-call policy
adjudication evaluates the bounded controller reversal.

## DD-219 and DD-220 controlled-response adjudication

DD-219 freezes a property-free policy for evaluating the saved DD-218 response
as a controlled terminal-inventory trajectory instead of requiring inventory
to increase forever. Its calculations complete, but result serialization
aborts on a NumPy boolean scalar. No scientific result or live call is made.

DD-220 preserves DD-219's evidence, thresholds, calculations, and gates. Its
only change converts NumPy scalar values to native JSON scalar values before
serialization. The single execution passes every gate with zero model,
provider, solver, timestep, or trajectory calls.

The accepted response accumulates only `0.267037 lbmol`, peaks at `280 s`, and
then declines through four final samples as the bottoms controller increases
withdrawal. Both terminal levels remain physical, every DD-218 root and
nonresponse gate remains passed, and inventory recurrence remains exact. This
accepts the existing DD-218 science as a five-minute controlled dynamic run; it
does not alter DD-218's frozen formal label or claim validation of a larger
production column.

## DD-221 full C3/C4 structural migration

The full source topology contains 20 physical locations with feed on stage 12.
Core V3 represents them as a reflux drum, ten generic rectifying volumes, one
feed volume, seven generic stripping volumes, and a combined reboiler/sump.
The generic topology builder maps stages 1 through 20 exactly once without
adding source-stage conditionals to equation code.

Every structural layer remains square and full-rank: the provider-governed
registry is `160 x 160`, the uncontrolled dynamic DAE is `158 x 158`, and the
terminal-controlled DAE and BDF2 step are both `162 x 162`. BDF2 retains 164
complete history values across component inventories, derived energies, and
controller memory. Component and energy telescoping remain structural
invariants.

The full pattern exposed an audit-performance defect in SciPy structural
matching. Core V3 now uses an exact deterministic Hopcroft-Karp matcher for
these structural audits, with regression equivalence on smaller patterns. No
model equation or numerical residual changes. DD-221 is property-free and
does not establish a full-column root; the next boundary is a frozen live
residual and Jacobian readiness audit at a clearly labeled source-derived
audit point.

## DD-222 full C3/C4 live readiness

The full source mapper now transfers all 20 liquid holdups, liquid and vapor
compositions, temperatures, pressures, liquid and vapor flows, feed, products,
duties, and hydraulic geometry into the same generic Core V3 numerical
contract used by the reduced model. The reflux-drum temperature and incipient
vapor are reconstructed from DWSIM PR fugacity equality, and condenser energy
closure gives `Q_C = -49.640294 MMBTU/h`. This reconstruction does not promote
the source workbook profile to an accepted steady root.

The `160 x 160` live Jacobian has only 15 structural colors. Two colored
central-difference matrices plus 17 individually differenced sentinel columns
therefore require 97 residual evaluations instead of 643 for two complete
uncolored matrices. The sentinel columns cover the first and last coordinate
in every repeated state/flow family plus both products and condenser duty.
Every sentinel agrees exactly with the colored matrix at the audit point.

Both live matrices are full rank with condition `3.080727e6`, stable spectra,
complete condenser rank, and no missing registered coupling. Conservation and
provider semantics pass. The source residual is finite but not small:
`0.547063` scaled, led by Francis liquid-hydraulic mismatches in the stripping
section. The architecture is therefore live-ready, while the imported profile
still requires a bounded full-column stationary solve before it can initialize
dynamics. DD-222 authorizes that one frozen solve campaign only.

## DD-223 full C3/C4 stationary-root stop

The full stationary campaign applies the validated 15-color Jacobian to two
independent 160-coordinate starts under the same transformed bounds and
DWSIM-PR equations. Coloring reduces each derivative matrix from 320 to 30
residual evaluations and keeps the complete two-start run to 236,304 logical
property calls in `50.383 s`.

Neither start establishes a root. The source-derived start improves the scaled
residual from `0.547063` to `4.309924e-4`, while the independent smooth start
stops at `1.231733e-2`. Their endpoints differ physically by `9.127158e-2`.
Both remain positive, ordered, conservative, and away from bounds, but the
live Jacobians become ill-conditioned (`1e9-2e10`) and step-sensitive. Thus
the result is not a blow-up or a structural-rank failure; it is failure of the
frozen direct bounded least-squares architecture to reach a reproducible root.

The source endpoint's provisional `D=2458.205`, `B=4701.618 lbmol/h`, and
`Q_C=-50.290339 MMBTU/h` are diagnostic only. They are not accepted products,
an initializer, or a dynamic starting state. DD-223 prohibits a retry,
continuation, tolerance adjustment, or another direct-solver variation.
Full-column dynamics remain stopped pending a separately governed static
diagnosis or a materially different solver architecture.

## DD-224 diagnostic-evidence boundary

DD-223 retained enough evidence to prove failure, but not enough to localize
it. The artifact includes endpoint coordinates, physical states, block norms,
ranks, conditions, and singular values. It does not include individual
residual rows or complete Jacobian matrices, so left/right singular directions
and weak equation-variable combinations cannot be recovered after the fact.

DD-224 makes no model, property, residual, Jacobian, solver, or timestep call.
It preserves DD-223's failed classification and authorizes only an exact
read-only replay of the two saved endpoints. That replay may capture the
missing vectors and matrices but may not solve, modify, or advance either
state.

## DD-229 explicit density-routing parity

DD-229 evaluates the complete full-column residual and two colored Jacobians at
both DD-223 endpoints with explicit mixed property ownership. DWSIM supplies
imposed-phase fugacity and phase enthalpy. The parameter-aligned PR provider
supplies liquid density from its smallest positive root.

This removes the false hydraulic derivative. All matrices retain rank 160;
conditions are `4.02e5-3.36e6`, spectrum changes are below `4e-9`, and complete
matrix changes between finite-difference steps are about `1.5e-10` relative.
The complete matrices are stored in compressed NPZ evidence rather than large
expanded JSON arrays.

The old endpoint residuals increase because their liquid flows were fitted to
the discontinuous DWSIM density branches. They remain starting guesses only.
One zero-call fixed coordinate-scaling design may use the four accepted DD-229
matrices before a new root campaign is considered.

## DD-230 fixed full-column coordinate scaling

DD-230 derives one coordinate scale from all four DD-229 matrices. Each scale
is the inverse geometric-mean norm of that coordinate's Jacobian column across
both endpoints and both finite-difference steps. The vector is normalized to a
geometric mean of one and is fixed before any solve.

The scale range is only 8.813:1. It improves all four conditions by 1.80-1.96x,
leaving them between `2.05e5` and `1.86e6`. The design makes no live call and
does not change residual scales or physical equations.

One new stationary-root campaign may combine the explicit DD-229 density
routing with this exact coordinate scale. No dynamic integration is authorized
until that campaign reaches one common accepted physical root.

## DD-231 accepted full-column stationary root

DD-231 combines the explicit DD-229 density routing and fixed DD-230 coordinate
scale with the unchanged full-column equation system. Both independent starts
converge to one common root with residuals below `9e-14` and physical agreement
of `5.95e-13`. Endpoint matrices retain rank 160 and condition about `6.20e5`.

The stationary flow solution is `D=2431.550` and `B=4711.424 lbmol/h`, with
`Q_C=-50.0522 MMBTU/h` and specified `Q_R=54.7060 MMBTU/h`. Distillate propane
and butane fractions are `0.897031/0.102937`; bottoms propane is `0.042411`.

This establishes a reproducible full-column algebraic root. It does not itself
create dynamic history or authorize a timestep. The next architecture task is
to map this root into the controlled BDF2 DAE state and history contract while
retaining explicit DWSIM fugacity/enthalpy and aligned-PR density ownership.

## DD-225 read-only endpoint evidence capture

DD-225 re-evaluates the two exact DD-223 endpoints using the unchanged Core V3
full-column equations, DWSIM PR provider, fixed residual scales, 15-color
structure, and central-difference steps. It stores each complete residual
vector and each complete scaled Jacobian matrix together with row, block, and
coordinate ledgers and full singular vectors.

The replay reproduces DD-223 exactly at the saved summary level: residual-norm
and singular-spectrum differences are all zero, and all four matrices retain
rank 160. It uses 12,474 logical provider calls in 6.169 seconds. It does not
invoke a nonlinear solver or alter or advance either endpoint. The resulting
artifact is diagnostic evidence only and is not an initializer or a dynamic
state.

## DD-226 full-column conditioning localization

DD-226 reads only the complete DD-225 evidence. It performs no model or
provider evaluation. The analysis separates the DD-223 conditioning failure
into two numerical effects.

The step-sensitive largest singular value comes from one local derivative:
the Francis hydraulic residual in `stripping_volume_6` with respect to that
volume's temperature. Halving the finite-difference step nearly doubles the
entry. The weakest singular direction is instead a composition/material
balance chain, dominated by n-pentane through the reflux drum and rectifying
section. Diagnostic row-and-column equilibration lowers matrix conditions from
billions to roughly 600-1,300.

This result does not authorize a new root solve. A direct, one-coordinate
perturbation must first determine whether the unstable hydraulic derivative is
caused by colored-Jacobian grouping or by the underlying property/hydraulic
evaluation. Physical equation changes remain unauthorized.

## DD-227 direct hydraulic-derivative diagnosis

DD-227 perturbs only the coordinate selected from DD-226's evidence. Direct
one-column derivatives reproduce the saved colored entries exactly, clearing
the structural coloring implementation.

The discontinuity is in DWSIM's declared liquid density. Temperature changes
of only a few millionths of a degree switch the returned density between
roughly 0.46-0.47 and 0.57-0.58 lbmol/ft3. That nonphysical jump propagates
through liquid volume, height, weir head, and Francis flow. It explains the
large, step-dependent Jacobian entry and the inflated condition number.

The Francis relationship itself remains unchanged. Before another full-column
Jacobian or root solve, a phase-explicit density calculation using the same PR
parameters must be tested for smoothness and physical agreement. A provider
change is not yet authorized.

## DD-228 phase-explicit density candidate

The independent, parameter-aligned PR validator now exposes ordered physical
compressibility roots and a liquid molar density calculated from the smallest
positive root. This is a validation capability only; the governing residual
continues to use DWSIM density.

At all DD-227 sample states, the candidate returns one smooth density near
0.504 lbmol/ft3. Its central-difference derivative is stable across four step
sizes to better than `5e-10` relative spread. No DWSIM call is needed for this
check.

The next authorized parity audit may use explicit property-level routing:
DWSIM remains responsible for imposed-phase fugacity and phase enthalpy, while
the aligned PR provider supplies liquid density. That routing must be recorded
as such and is not a silent fallback. No root or timestep is authorized.

## DD-232 full-column dynamic handoff

The accepted DD-231 stationary root now has a complete property-free mapping
into the full controlled dynamic ledger. Its liquid amounts and compositions
become 60 component inventories. Temperatures, equilibrium compositions,
liquid and vapor flows, bubble composition, and condenser duty become 98
dynamic algebraic coordinates. The accepted distillate and bottoms rates are
the two bumpless controller references.

The dynamic seed uses zero component rates, zero PI rates, zero PI memories,
and zero product log ratios. Both BDF2 component-history levels contain the
same accepted inventories. The BDF2 contract also owns 40 internal-energy
history values and four PI-memory history values, for 164 complete history
coordinates. A moving BDF2 calculation will still require one accepted
backward-Euler startup step.

Internal-energy values and terminal level setpoints are not guessed in the
property-free mapping. The next live audit must reconstruct them at the
accepted root using DWSIM phase enthalpy and the aligned-PR smallest-root liquid
density, copy identical energies into both history levels, and use the exact
geometry-derived levels as the initial setpoints. It must then verify zero
motion and a full-rank leading Jacobian. No timestep is authorized by DD-232.

DD-233 completes that live audit. At identical current and prior histories, the
full controlled BDF2 residual is `8.26e-14` and every component, energy, and PI
rate is exactly zero. The reconstructed top and bottom levels are 43.96% and
52.84%. Both scaled `162 x 162` leading Jacobians have rank 162 and condition
about `5.80e6`; their spectra are stable and 15 direct-column checks match the
colored assembly exactly. The accepted stationary root is therefore a clean,
numerically regular dynamic handoff under the governing provider split.

This is still a zero-time result. The next gate is one stationary hold step,
which must return the same state within frozen tolerances before any disturbance
or moving trajectory is permitted.

DD-234 passes that hold-step gate. One `0.25 s` backward-Euler startup step and
two `0.125 s` refinement steps all return the accepted state exactly in saved
arithmetic. Their residuals remain `8.26e-14`, all Jacobians retain rank 162,
and the worst scaled condition is `1.05e7`. No inventory, energy, algebraic,
controller, product, or level motion is introduced by the first full-column
time advance.

The accepted `0.25 s` endpoint and the DD-233 state now form a valid two-level
history pair for a first moving BDF2 step. Only one small, separately frozen
disturbance step is authorized next; a trajectory is not yet authorized.

DD-235 passes the first moving-step gate. Feed component rates and total feed
enthalpy are increased together by 0.1%, preserving composition and specific
enthalpy. One `0.25 s` backward-Euler step and two `0.125 s` refinement steps
all converge with residuals below `1.28e-12`, full rank 162, and worst condition
`1.05e7`.

The column accumulates `4.960399e-4 lbmol` over the quarter second, exactly the
small positive response expected from the external component balance. The
full and refined endpoints differ by at most `2.49e-6 lbmol` in any component,
and the component inventory identity closes below `4.43e-13 lbmol`. Equilibrium,
energy and component conservation, discrete kinematics, controller equations,
and provider ownership all remain valid.

This establishes a locally accurate moving response for the complete 20-stage
controlled model. It authorizes one separately frozen short trajectory using
the same 0.1% feed disturbance. It does not yet establish sustained dynamic
stability, controller quality, or long-run performance.

## DD-236 vapor-holdup successor boundary

The DD-235 trajectory authorization is superseded by the newly recognized
vapor-holdup requirement. The accepted Core V3 V1 model remains immutable as a
reduced-order historical result; no additional V1 trajectory is authorized.

DD-236 starts a separately versioned equilibrium-stage successor. Every
physical control volume now has distinct conserved liquid and vapor component
states, `N_L[j,k]` and `N_V[j,k]`. Vapor composition is derived only from
`N_V/sum(N_V)` and is not an independent algebraic variable. Equal-and-opposite
`M_VL[j,k]` coordinates own phase transfer. The structural equations include
separate liquid and vapor component balances, full fugacity equilibrium,
Francis liquid hydraulics, vapor EOS/free-volume closure, pressure-driven vapor
links, one top pressure anchor, and total energy storage `U_L + U_V`.

The five-volume/three-component development system has 30 conserved states and
a square, full-rank `63 x 63` implicit ledger. The 20-volume C3/C4 topology has
120 conserved states and a square, full-rank `258 x 258` ledger. Structural
audits reject missing/nonpositive volume, unowned vapor states, independent
vapor composition, uncancelled phase transfer, duplicate pressure ownership,
provider fallback, and liquid-only energy storage.

DD-236 is property-free. Its positive volume declarations are structural test
values, not accepted physical geometry. The next layer must obtain real tray,
drum, and reboiler/sump free-volume geometry and implement provider-owned vapor
compressibility, vapor enthalpy/internal energy, liquid displacement, and the
live EOS residual. No root, timestep, controller, or trajectory is yet
authorized for the vapor-holdup successor.

DD-237 replaces the structural volume values with physical C3/C4 workbook
geometry. Tray gross capacity is stage area times tray spacing. The reflux drum
uses its 12.1 ft diameter, 36.3 ft tangent length, and two hemispherical heads.
The combined bottom volume uses the 18.1759 ft diameter, 12 ft high vertical
sump plus the declared stage-20 reboiler vapor extension.

The resulting gross capacities are `5101.729438 ft3` at the top,
`338.945707-1129.819023 ft3` for tray bays, and `3405.501240 ft3` at the
bottom. These are not fixed endpoint vapor spaces. The governing definition is

`V_free[j] = V_gross[j] - sum_k(N_L[j,k]) / rho_L[j]`.

All 20 source stages map exactly once, and inserting the physical capacities
retains the full-rank `258 x 258` structural ledger. DD-237 remains
property-free; live liquid density, vapor compressibility, vapor enthalpy, and
the numerical EOS residual are the next implementation boundary.

DD-238 crosses that live-property boundary without changing the historical V1
model. At the accepted DD-231 state, aligned parameter-specific PR supplies
liquid density, while DWSIM supplies vapor compressibility and both phase
enthalpies. Free volume includes live liquid displacement, and resident vapor
inventory is reconstructed from

`N_V[j] = P[j] * V_free[j] / (Z_V[j] * R * T[j])`.

The 20-volume column contains `473.563386 lbmol` of resident vapor and
`2909.337841 lbmol` of liquid. Vapor therefore represents about 16.3% of the
liquid mole inventory, confirming that its prior omission was material. Every
volume has positive free space and vapor inventory. The maximum relative EOS
residual is `1.122839e-16`; all 80 expected provider calls are present and no
fallback occurs. Stored energy is now evaluated as `U_L + U_V` using a
consistent `U=H-PV` conversion for each phase.

DD-238 reconstructs a consistent vapor state only. It does not yet balance
liquid and vapor separately, calculate interphase transfer, or evaluate the
complete `258 x 258` successor residual. That full two-phase residual is the
next boundary; no root, timestep, controller, or trajectory is authorized.

DD-239 implements the conservation core of that residual. Liquid and vapor
transport are assembled independently. A positive `M_VL[j,k]` transfers a
component from vapor to liquid, entering the liquid equation positively and
the vapor equation negatively. At the accepted stationary root, local vapor
transport determines the required phase-transfer vector; the separate liquid
equation then closes without changing the state.

For the full 20-volume case, vapor residuals are exactly zero, the worst
liquid/total component residual is `1.055384e-9 lbmol/h`, and the worst energy
residual is `9.220093e-8 BTU/h`. Global transport telescopes to the external
component and energy rates within `2.842171e-13 lbmol/h` and exactly zero,
respectively. Interphase transfer cancels exactly.

This proves that explicit vapor storage and phase transfer are compatible with
the accepted stationary balance. The next implementation must assemble these
rows with full fugacity equilibrium, EOS, Francis hydraulics, pressure-drop,
and pressure-anchor rows in the complete 258-equation numerical residual.
