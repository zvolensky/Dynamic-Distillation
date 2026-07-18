# Dynamic Model Current State

Date: 2026-07-12
Updated: 2026-07-17

Status: Authoritative current-state summary. This supersedes `docs/dynamic_model_current_state_2026-07-08.md` for current decisions while retaining that document as historical evidence.

## 2026-07-17 frozen-closure addendum

DD-065 converted the accepted 2400-second C3/C4 checkpoint to frozen interior
component totals and total internal energy, using checkpoint phase inventories
only as initial guesses. All 18 active interior trays passed the local DWSIM
Peng-Robinson UV reconstruction gates, with maximum relative component,
energy, and volume residuals of `5.78e-11`, `4.73e-12`, and `1.15e-10`.

The column-wide pressure/liquid-flow/vapor-flow solve did not converge:
liquid- and vapor-flow scaled residuals were `1.0545` and `6.8154`, local UV
pressure disagreed with the attempted global solution by as much as
`86.78 psi`, and all 18 interior liquid and vapor profile/previous-flow
limiters were active. The local UV pressure implied by frozen checkpoint
totals also ran in the wrong overall direction, from `321.89 psia` at stage 2
to `205.16 psia` at stage 19, while the checkpoint hydraulic profile rose from
about `225.11` to `232.18 psia`.

DD-066 subsequently completed terminal conserved-inventory ownership for the
total-condenser placeholder, reflux drum, partial reboiler, and bottoms sump.
Whole-column terminal bookkeeping closes to numerical precision. Independent
top and bottom terminal UV closure still produces reversed pressure ordering:
`P_top=213.564 psia` and `P_bottom=199.616 psia`.

DD-067 then held every node component inventory and fixed volume constant,
redistributed only internal energy, and recovered an ordered 20-node local UV
profile while preserving whole-column energy to `1.84e-9` relative error.
This proves conservative local-state feasibility, but the pressure-isotonic
construction moved `9.32%` of energy inventory on an L1 basis, changed one
pressure by `93.66 psi`, and did not include hydraulics. It is therefore an
existence proof, not a usable initializer.

DD-068 allowed both component inventory and internal energy to move under
exact global conservation and minimized normalized L2 movement. Two of five
starts reproduced the same objective to `2.57e-9` relative spread, but three
starts failed. The best candidate moved `1,012,849 BTU`, retained a maximum
pressure correction of `79.159 psi`, and concentrated `80.3%` of absolute
energy movement in the terminal assemblies. Its top terminal was about
`60 psi` below the first interior tray. This is a reproducible local basin,
not a robust global least-movement solution.

DD-069 then falsified several possible explanations. The `U=H-PV` conversion,
phase aggregation, mapped-energy provenance, and eliminated condenser
placeholder are correct. The checkpoint phase states do not fill the mapped
control volumes or reproduce live DWSIM enthalpy: the sump volume mismatch is
`51.47%`, representative interior volume mismatches are `17%` to `38%`, and
stored-H mismatch reaches `233%`. DD-068 also prices the same `1000 BTU`
terminal move at only `0.000418` to `0.002956` times the median interior cost.
Its terminal concentration is therefore partly an objective-scaling artifact.

DD-070 performed that one bounded repeat. It rebuilt internal energy from live
DWSIM phase properties, selected a liquid-only sump topology, and used common
whole-column movement scales. The best candidate improved to `159,739 BTU`
of energy movement and `23.335 psi` maximum pressure correction, but only one
of five starts converged. The checkpoint enthalpy mismatch is state-dependent,
not a constant reference offset. Checkpoint repair is therefore retired.

The architecture conclusion is now decisive: conserved-state local thermo is
viable, but production initialization must use a direct steady-state
conserved-state solve from operating specifications. Do not retune checkpoint
projection or add hydraulics to the DD-070 candidate. See
`docs/dd_065_frozen_checkpoint_uv_hydraulic_closure_20260717.md`,
`docs/dd_066_terminal_conserved_inventory_mapping_20260717.md`,
`docs/dd_067_conservative_energy_redistribution_probe_20260717.md`,
`docs/dd_068_least_movement_redistribution_20260717.md`, and
`docs/dd_069_terminal_energy_volume_basis_audit_20260717.md`, and
`docs/dd_070_canonical_checkpoint_repair_20260717.md`.

DD-071 has now registered that direct system structurally. Treating the
partial reboiler and sump as separate conserved nodes leaves one unowned
reboiler-to-sump liquid flow (`291` unknowns versus `290` residuals). The
DD-070-compatible combined bottom control volume removes that internal
transfer without inventing an equation and produces a square, structurally
full-rank `281 x 281` registry. Numerical residual, telescoping, and Jacobian
evaluation were the next bounded work. DD-072 now evaluates all `281`
residuals directly with live DWSIM PR, closes component and energy telescoping
near machine precision, and finds numerical rank `281` at ChemSep and a
bounded perturbation for both finite-difference step sizes. The uncolored
reference finds no missing registered dependencies. Condition estimates remain
high, so only a staged bounded continuation is authorized next. See
`docs/dd_071_direct_steady_state_registry_20260718.md` and
`docs/dd_072_direct_steady_state_numerical_audit_20260718.md`.

DD-073 implemented the approved five square continuation stages, smooth
physical-domain coordinates, adaptive trust-region lambda schedule, accepted
state retention, and rank/condition gates. The implementation tests pass, but
two live DWSIM PR paths stop in Stage 1. The paths remain rank `160/160`,
conservative, and safeguard-free; separate Stage 1 endpoint solves with
sparse and dense linear algebra retain full rank but leave a scaled residual
floor near `2.1e-4`. The failure is distributed across local component and
energy reconstruction. The current Stage 1 holds ChemSep-derived conserved
`N/U` fixed while changing phase states to the DWSIM basis, so full rank does
not establish endpoint feasibility. Do not tune the lambda path or lower
tolerances. Revise the release ordering so conserved and phase states move
together before another direct solve. See
`docs/dd_073_direct_steady_state_continuation_20260718.md`.

DD-074 completed that final release-order audit without a live solve. The
merged local/conserved stage has the required `240` unknowns and `240`
physical residuals, exact variable-coordinate anchors, exact DD-072
lambda-one identity, and machine-precision conservation. Its physical
structural rank is only `239`, with one unmatched bottom vapor inventory and
bottom heavy-component balance. The later `258/277/281` systems recover full
rank, but promoting hydraulics into another first-stage variant is prohibited
by the DD-074 hard stop. Manual staged continuation is retired. The next
architecture must address the complete physical system at once, use
pseudo-transient or DAE/nonlinear methods with stronger derivatives, or
validate a reduced column before returning to the full case. See
`docs/dd_074_merged_continuation_structural_audit_20260718.md`.

DD-075 then performed the one authorized reduced-column feasibility study
before any full-system pseudo-transient investment. The deterministic
five-volume case retained the same direct conserved equations, live DWSIM PR,
Francis hydraulics, vapor pressure drop, feed/products, and terminal
specifications. It is square and structurally full rank at `71 x 71`; all
four initial numerical Jacobians are also rank `71`, with condition estimates
between `2.45e7` and `2.92e7`. The numerical gate therefore authorized two
fixed trust-region and two fixed pseudo-transient attempts from the ChemSep
and smooth perturbed seeds.

None reached the required scaled physical residual below `1e-7`.
Trust-region stopped near `0.035`, dominated by steady component balances,
and one endpoint lost numerical rank. Pseudo-transient stopped near `0.465`,
with liquid hydraulics, component balances, and vapor pressure drop still
open. All endpoints remained positive, pressure ordered, conservative,
safeguard-free, and unsaturated. This is not a proof that no mathematical
root exists, but it is the predefined stop result: the present direct
conserved formulation is retired as a production initializer architecture,
and a `281`-variable pseudo-transient program is not authorized. See
`docs/dd_075_reduced_column_feasibility_20260718.md`.

## Executive assessment

The repository now contains a credible, numerically stable, controlled C3/C4 operating checkpoint and a strong supporting platform for thermo integration, controls, diagnostics, continuation, reporting, and model investigation.

It is not yet acceptable to call the full C3/C4 model a rigorous physical steady-state simulation. DD-058 is an operational development baseline, not a completed equilibrium-stage validation.

## Current operational baseline

Preferred run: `logs/c3c4_dd058_extended_composition_settle_hold300s_r2_20260712`

Preferred checkpoint: `c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_20260712_110933.npz` in that run folder.

| Metric | DD-058 endpoint |
|---|---:|
| Dynamic score | 0.0848, PASS |
| Maximum relative state rate | 0.000254/s |
| Top pressure | 221.871 psia |
| Condenser duty | -49.163 MMBtu/h |
| Distillate flow | 2254.42 lbmol/h |
| Distillate n-butane | 0.063691 mole fraction |
| Top level | 51.967% |
| Bottom level | 49.842% |
| Global mass-closure error | -2.22e-12 lbmol/h |

The normalized equilibrium-target gate passed, the live vapor-material rates were small, pressure and levels were controlled, and the successive DD-053 through DD-058 holds showed monotone score improvement. This state is suitable for continuation, controller work, reporting, and controlled diagnostic experiments.

## What is established

- DWSIM Peng-Robinson is the current trusted runtime thermo backend for this hydrocarbon case.
- The Clapeyron adapter now rejects inactive duplicate flash rows rather than manufacturing unit K-values, but Clapeyron remains outside the accepted runtime path pending a suitable public single-phase/stability API.
- Product draws use live drum and sump compositions.
- Feed-flash mode is propagated into every runtime `ColumnInputs` instance.
- Total-condenser excess duty is routed to energy removal/subcooling rather than unbounded vapor consumption.
- Geometry-based top and bottom level controllers operate successfully.
- Native checkpoints preserve substantially more usable continuation state than Excel restart workbooks.
- Global material conservation is excellent.
- The dynamic, normalized-equilibrium, thermo-health, and operating-point audits provide useful evidence and prevent several classes of false acceptance.

## Remaining physical blocker

DD-058's used tray liquid rates form nearly exact section-wise plateaus:

- above the feed: approximately the fixed reflux rate,
- below the feed: approximately reflux plus the all-liquid feed.

This is not an independently predicted rigorous liquid-traffic profile. It results from two current model choices:

1. liquid outflow is still a `25%` Francis prediction blended with `75%` imported profile ownership;
2. `composition-exponential` equilibrium correction preserves phase totals and therefore supplies essentially no net tray evaporation or condensation.

DD-060 tested a direct full TP-flash phase-total exponential update. It failed in one `0.2 s` step (`score=821`) because fixed-temperature/pressure phase targets demanded large phase changes without simultaneous latent-energy closure. Representative energy-conserving UV solves converged, but exposed competing pressure ownership. For example, stage 19 reported:

- hydraulic pressure: `232.18 psia`,
- vapor-holdup implied pressure: `293.85 psia`,
- isolated UV-consistent pressure: `268.67 psia`.

The model can therefore carry hydraulic pressure and explicit vapor inventory that describe different thermodynamic states. Controller tuning, relaxation tuning, initializer optimization, or simply setting Francis `alpha=1` cannot resolve that structural inconsistency.

## Initialization position

ChemSep and Excel profiles remain useful seeds and comparison references. They are not runtime truth and are not guaranteed model-consistent initial conditions.

Least-squares residual solvers, profile projections, homotopies, and boundary reconciliation remain useful diagnostics. They must not be presented as the primary solution while the runtime equations have competing physical owners. An initializer cannot produce a rigorous zero-residual state for an internally inconsistent equation set.

DD-058's native checkpoint is the preferred operational restart artifact. It is not a rigorous golden steady-state seed.

## Architecture decision after DD-075

The DD-060 through DD-075 conserved direct formulation is no longer the
recommended implementation path. Do not continue it through another reduced
topology, tray-count ladder, release order, solver sweep, or full-column
pseudo-transient campaign.

A future rigorous model should restart from a simpler equilibrium-stage
foundation with a known independently reproduced steady solution. Conserved
energy, terminal volumes, pressure ownership, vapor pressure drop, and Francis
hydraulics should be introduced in separately solvable increments, each with
its own structural, numerical, conservation, and dynamic gate before the next
physical block is added.

That redesign must remain isolated. The accepted DD-058 implementation and
defaults remain frozen as the operational development baseline, and the
validated source-topology model remains the correctness anchor.

DD-076 defines that redesign before implementation. The selected family is
an equilibrium-stage DAE, not a rate-based model. Its first layer prescribes
pressure, neglects tray vapor holdup, stores total component inventory and
internal energy, solves temperature and equilibrium compositions
algebraically, gives Francis hydraulics sole ownership of tray liquid flow,
and uses prescribed section vapor rates. The contract defines the
total condenser, reflux drum, interior trays, combined reboiler/sump,
governing equations, operating degrees of freedom, explicit exclusions,
phased gates, and stop rules. See
`docs/dd_076_equilibrium_dae_v2_architecture_contract_20260718.md`.

DD-077 implements the first isolated structural registry. Its initial
`51 x 51` form exposed two free terminal inventory modes. The corrected steady
specification fixes drum and bottom liquid amounts and solves `D/B`, yielding a
`53 x 53` registry with full structural rank, exact symbolic component and
energy telescoping, prescribed pressure and section vapor rates as parameters,
and Francis ownership of every tray liquid-flow unknown. No live properties,
nonlinear solve, or integration were attempted. See
`docs/dd_077_core_v2_structural_registry_20260718.md`.

DD-078 implements the first numerical v2 equation assembly. The property-free
binary source equations match the accepted independent Skogestad translation
within `5.6e-16` for nominal, feed-step, and perturbed states. Global material
balances close to roundoff, and the published steady profile evaluates at
`3.7e-8 /min`, inside the declared `1e-7 /min` tabulation gate. This passes the
residual portion of Gate A; dynamic integration has not yet been attempted.

The repository's existing `sandbox/mini8` case will be leveraged in later
gates for its compact workbook, C3/C4 data, geometry, UV state-building
patterns, and conditioning-audit patterns. Its profile was sampled from the
old 20-stage model, so neither that profile nor its historical trajectories
are independent acceptance references for v2. See
`docs/dd_078_core_v2_source_equation_gate_20260718.md`.

DD-079 completes Gate A. Nominal profile drift, the immediate `+1%` feed
step, and the deterministic bounded state perturbation all complete `500 min`
with v2/reference normalized trajectory error at or below `3.85e-11`.
BDF/Radau agreement is at or below `1.60e-9`; total and light-component
solver-integrated conservation close below `2.77e-12`; every composition and
holdup remains physical; and no safeguard is activated. Product component
withdrawal follows the live terminal compositions. Gate B is now authorized
for one mini8 inventory volume with prescribed pressure and live DWSIM
property/energy closure. See
`docs/dd_079_core_v2_gate_a_dynamics_20260718.md`.

DD-080 completes Gate B. One role-selected mini8 feed volume reconstructs
liquid amount/composition directly from conserved component inventory and
reconstructs temperature plus equilibrium-vapor composition from canonical
live DWSIM PR internal energy and phase fugacity coefficients. The canonical
state and four bounded perturbations converge from three guesses with full
`3/3` rank and condition below `3`. Live-density geometry is physical. Four
short BDF/Radau dynamics pass with worst normalized method disagreement
`3.75e-9`, component conservation `4.60e-16`, and energy conservation
`2.01e-16`. Gate C is authorized but not yet implemented. See
`docs/dd_080_core_v2_gate_b_one_volume_20260718.md`.

## Acceptance language

Use these descriptions consistently:

- **Accepted operational baseline**: DD-058 is bounded, controlled, restartable, and dynamically quiet under its current recipe.
- **Not yet physically validated**: tray liquid traffic and pressure/vapor-holdup ownership are not yet rigorous.
- **Retired initializer architecture**: DD-060 through DD-075 conserved direct
  steady-state and manual continuation work is preserved as diagnostic
  evidence but is not authorized for additional solver development.
- **Selected replacement architecture**: DD-076 equilibrium-DAE v2 has an
  architecture and equation-count contract; DD-077 begins its isolated
  implementation but does not yet establish numerical or dynamic validity.
- **V2 structural gate**: DD-077 passes topology, ownership, equation-count,
  structural-rank, and symbolic-conservation checks only.
- **V2 source-equation residual gate**: DD-078 passes independent residual
  parity and material conservation.
- **V2 Gate A dynamics**: DD-079 passes independent trajectory parity,
  integrated conservation, exact event scheduling, physical-domain, and
  integrator-refinement checks.
- **V2 Gate B one-volume closure**: DD-080 passes canonical live DWSIM
  energy/fugacity reconstruction, predefined perturbations, root consistency,
  numerical rank, geometry, local dynamics, and energy/component
  conservation. Five-volume Gate C is authorized but remains unproven.

## Supporting documents

- `docs/dd_055_dd057_composition_settling_baseline_20260712.md`
- `docs/dd_060_physics_owned_tray_flow_probe_20260712.md`
- `docs/dd_065_frozen_checkpoint_uv_hydraulic_closure_20260717.md`
- `docs/dd_066_terminal_conserved_inventory_mapping_20260717.md`
- `docs/dd_067_conservative_energy_redistribution_probe_20260717.md`
- `docs/dd_075_reduced_column_feasibility_20260718.md`
- `docs/dd_076_equilibrium_dae_v2_architecture_contract_20260718.md`
- `docs/dd_077_core_v2_structural_registry_20260718.md`
- `docs/dd_078_core_v2_source_equation_gate_20260718.md`
- `docs/dd_079_core_v2_gate_a_dynamics_20260718.md`
- `docs/gates_explained.md`
- `docs/issue_log.md`
- `docs/model_architecture.md`
- `docs/initializer_requirements_and_acceptance.md`
