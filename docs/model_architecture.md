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
