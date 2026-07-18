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

## Required next architecture

The defensible physics path is an isolated model-core experiment with:

1. conserved tray component totals and total internal energy as differential states;
2. a coupled UV/volume algebraic solve for temperature, pressure, phase fraction, and equilibrium compositions;
3. Francis hydraulics determining liquid outflow from the solved liquid inventory and geometry;
4. vapor traffic and pressure solved in the same closure so pressure and vapor holdup have one owner;
5. imported tray flows used only as initial guesses and independent validation comparisons.

This work must remain on an isolated branch or sandbox until it passes single-stage, small-column, and full-column gates. The accepted DD-058 implementation and defaults should remain frozen during that investigation.

## Acceptance language

Use these descriptions consistently:

- **Accepted operational baseline**: DD-058 is bounded, controlled, restartable, and dynamically quiet under its current recipe.
- **Not yet physically validated**: tray liquid traffic and pressure/vapor-holdup ownership are not yet rigorous.
- **Experimental diagnostic**: DD-060 `phase-exponential`, least-squares initializer variants, and UV/DAE prototypes.

## Supporting documents

- `docs/dd_055_dd057_composition_settling_baseline_20260712.md`
- `docs/dd_060_physics_owned_tray_flow_probe_20260712.md`
- `docs/dd_065_frozen_checkpoint_uv_hydraulic_closure_20260717.md`
- `docs/dd_066_terminal_conserved_inventory_mapping_20260717.md`
- `docs/dd_067_conservative_energy_redistribution_probe_20260717.md`
- `docs/gates_explained.md`
- `docs/issue_log.md`
- `docs/model_architecture.md`
- `docs/initializer_requirements_and_acceptance.md`
