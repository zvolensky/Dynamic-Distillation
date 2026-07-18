# Dynamic Distillation Requirements

## 1. Document Control
- Title: Dynamic Distillation Requirements Specification
- Version: 1.9
- Date: 2026-07-18
- Basis: Current implementation and tests in this repository.

## 2. Scope
This specification captures the as-built behavior of the current codebase plus explicit acceptance requirements identified by model-development evidence. Requirements that are not yet satisfied are called out in the notes and current-state document.

- `UR-*`: user-visible requirements.
- `FR-*`: functional/system requirements.
- Traceability links each requirement to implementation and test artifacts.

## 3. User Requirements
- `UR-001` Users shall be able to run dynamic distillation simulations from an Excel case through the Python CLI runner.
- `UR-002` Users shall be able to configure horizon and integration controls (`n_steps`, `dt`, logging cadence).
- `UR-003` Users shall be able to choose thermo execution mode (`stub`, `relative-volatility`, `clapeyron`, `dwsim`, DWSIM package aliases, `table`, `table-pool`) and thermo refresh strategy.
- `UR-004` Users shall be able to override key operating variables (reflux, boilup, condenser/reboiler duties, condenser pressure drop).
- `UR-005` Users shall be able to enable/disable control loops for level, top pressure, distillate composition, and bottoms composition.
- `UR-006` Users shall be able to enable top-drum PSV relief behavior and configure setpoint/gain/max vent.
- `UR-007` Users shall receive startup validation feedback split into blocking errors and non-blocking warnings.
- `UR-008` Users shall receive structured profile/summary CSV outputs when logging is enabled.
- `UR-009` Users shall be protected against accidental reruns of identical CLI commands unless explicitly overridden.
- `UR-010` Users shall have automatic run provenance tracking and experiment-ledger regeneration.
- `UR-011` Users shall be able to select runtime behavior mode (`parity`, `calibration`, `hydraulic`, `legacy`) from the CLI.
- `UR-012` Users shall be able to import and export richer Excel restart state, including boundary, energy, and controller memory sheets when present.
- `UR-013` Users shall be able to run source-topology validation cases that intentionally exclude standard boundary and vapor dynamic states when the validation source uses algebraic equivalents.
- `UR-014` Users shall be able to distinguish external steady-state seed data from accepted dynamic initial conditions, and shall have documented criteria for making a seeded column dynamic-ready.
- `UR-015` Users shall be able to distinguish a numerically quiet operational checkpoint from a rigorously physical dynamic solution whose tray flows, phase split, energy, pressure, and vapor inventory are mutually consistent.
- `UR-016` Users shall be able to distinguish local thermodynamic closure, global pressure/flow closure, and terminal-equipment closure, including an explicit result when a state is locally valid but outside the global algebraic constraint manifold.
- `UR-017` Users shall be able to distinguish mathematical feasibility of a conservatively redistributed state from an acceptable initializer, including the amount of component, energy, pressure, and temperature movement from the source checkpoint.

## 4. Functional Requirements

### 4.1 Case Loading and Validation
- `FR-001` The system shall load `.xlsx` case files and reject unsupported file types.
- `FR-002` The loader shall parse `Specifications`, `Initial Conditions`, and (best-effort) `Streams`.
- `FR-002a` The loader shall support optional restart-state sheets (`Boundary State`, `Energy State`, `Controller State`) when present.
- `FR-003` The loader shall canonicalize Excel component names to DWSIM-compatible component IDs.
- `FR-004` The system shall build a validated `ColumnSpec` and enforce stage/component consistency.
- `FR-005` The runner shall perform preflight validation and stop before integration on blocking errors.

### 4.2 State Initialization and Startup Conditioning

**Why Initialization Requires Explicit Attention**

The current v1 runtime implements an explicit-vapor, rigorous-energy
**sequential hybrid**, not a completed Index-1 DAE. Pressure, vapor holdup,
vapor flow, liquid flow, energy, and equilibrium targets are evaluated through
several ordered paths, some with previous-step feedback, profile blending, or
limiters. DD-060 through DD-075 show that these paths do not yet share one
consistent physical ownership structure. A future rigorous equilibrium-stage
implementation is expected to be a stiff DAE, but that is a target
architecture rather than an accurate description of the current runtime.

From the published literature on DAE initialization (Pantelides 1988; Barton, Biegler), a steady-state profile from an external tool (ChemSep, Aspen Plus, DWSIM) satisfies that source model's static equations. It does **not** automatically satisfy this model's topology, dynamic hydraulic equations, vapor-flow resistance, weir geometry, terminal inventories, pressure/volume constraints, or energy basis. When an incompatible state is launched directly, the first RHS evaluation can produce large derivatives or fail to lie on the algebraic constraint manifold.

Two separate initialization problems shall be recognized:
1. **DAE-consistent initialization**: hold specified independent variables and conserved differential states as required, then solve the algebraic equations so the state lies on the model's constraint manifold. Differential derivatives need not be zero.
2. **Steady-state initialization**: after algebraic consistency is established, solve the differential balances so all required inventory and energy derivatives approach zero while satisfying the same algebraic equations.

An initializer shall not report steady-state success merely because the algebraic block closes, and it shall not launch a dynamic smoke test from a state that fails algebraic consistency.

Initialization is not a trivial "switch to dynamics" operation; it is a distinct mathematical problem requiring structured root-finding, conservation audits, and acceptance gating. See `docs/dynamic_column_initialization_strategy.md` for mathematical foundation and workflow.

Requirements in this section define how external seeds are loaded, how initialization passes condition the column toward dynamic self-consistency, and what acceptance gates must pass before integration begins.


- `FR-006` The runner shall construct deterministic state layout and initial state vector from `ColumnSpec`.
- `FR-007` The runner shall initialize tray vapor holdup to match startup pressure profile assumptions.
- `FR-007a` In legacy explicit-phase restart mode, when `--use-excel-vapor-holdup` is enabled, the runner shall preserve explicit tray vapor holdup from the Excel `Initial Conditions` sheet through startup pressure initialization and thermo conditioning.
- `FR-007b` The runner shall support disabling dynamic tray vapor states for validation sources whose vapor composition is algebraic and whose equations do not include vapor holdup ODEs.
- `FR-007c` In rigorous conserved-state mode, imported or checkpoint liquid/vapor phase inventories shall be initial guesses only. The algebraic closure shall determine phase allocation, temperature, pressure, equilibrium compositions, and interstage flows while preserving the selected total component inventories and total internal energies.
- `FR-008` The runner shall support optional startup thermo-consistent conditioning iterations.
- `FR-009` The runner shall perform top-drum startup steadying pass for top-holdup residual reduction when top states are active.
- `FR-009a` When explicit runtime restart state is present, the runner shall skip vapor reseeding and startup conditioning/steadying steps that would overwrite the restart state.
- `FR-009b` External steady-state profiles, including ChemSep-derived profiles, shall be treated as initialization seeds unless a model-consistent residual audit or initializer demonstrates that the state is steady under this model's active topology, thermo, feed treatment, holdup states, and RHS equations.
- `FR-009c` Accepted dynamic initialization shall require block-level derivative/conservation checks in addition to any aggregate steady-state detector flag.
- `FR-009d` Initializer acceptance shall be conditional on a model-physics closure gate. An initializer shall not be expected to create a rigorous zero-residual state when the active runtime equations assign competing owners to pressure, phase totals, energy, or interstage flow.
- `FR-009e` Runtime steady-state acceptance shall include a whole-column inventory-rate criterion in addition to local state-rate criteria. A run with material `F-D-B` drift shall not pass solely because the drift is distributed across many tray states.
- `FR-009f` Initializer output shall distinguish at least: local thermodynamic closure failure; local thermodynamic closure success with global hydraulic failure; terminal-equipment mapping failure; algebraically consistent but dynamically non-steady; and fully accepted steady initialization.
- `FR-009g` A dynamic smoke test shall not be used to rescue or accept a candidate that fails the applicable local, global hydraulic, or terminal algebraic-closure prerequisite.

### 4.3 Thermodynamics Services
- `FR-010` The system shall support thermo providers for TP flash, phase enthalpy, and optional Z-factor diagnostics.
- `FR-010a` Rigorous equilibrium acceptance shall use either a direct phase-fugacity residual or a documented backend-certified equivalent. TP-flash phase-fraction consistency shall not be labeled as a fugacity residual when phase fugacity coefficients are unavailable.
- `FR-011` The system shall support tabular thermo from JSON surrogate tables.
- `FR-012` The system shall support process-pool tabular thermo mode for parallel batched stage flashes.
- `FR-013` The RHS shall use provider batch flash when available and fall back to scalar flash otherwise.
- `FR-014` The system shall support thermo refresh throttling by step cadence and optional per-stage `dT/dP/dx` thresholds.
- `FR-014a` The runner shall support optional live-PR override for the equilibrium-relaxation flash path while leaving the main thermo mode unchanged.
- `FR-014b` The system shall document optional external thermo dependencies and installation/setup steps for DWSIM/pythonnet, Python `thermo`, and Clapeyron/pyclapeyron backends.
- `FR-014c` The runner shall allow Clapeyron PR to use DWSIM PR component constants and binary interaction parameters when requested.
- `FR-014d` The runner shall provide a dependency-free `relative-volatility` thermo mode with constant-alpha VLE and simple enthalpy/Cp properties for validation cases with energy states.
- `FR-014e` The repository shall provide a Tier 1 source-topology validation workflow for Skogestad Column A using public source data and relative-volatility thermo, including steady-profile comparison, +1% feed-rate dynamic response comparison, and comparative plots.
- `FR-014f` When a run explicitly requests an external thermo backend, preflight or runtime shall fail clearly if that backend is unavailable. The runner shall not silently continue a nominal DWSIM or Clapeyron run using stale cached thermo packets after systematic backend failure.

### 4.4 RHS, Physics, and Closures
- `FR-015` The RHS shall compute tray/top/bottom component holdup derivatives with feed and boundary source terms.
- `FR-016` The model shall support condenser duty modes `total-condense` and `specified`.
- `FR-017` The model shall support pressure models `spec` and `hydraulic`, including optional condenser pressure drop.
- `FR-018` The model shall support vapor-flow models `profile`, `energy`, and `conductance` with reboiler-neighbor vapor guardrails.
- `FR-019` The model shall support optional equilibrium relaxation and optional energy-holdup states.
- `FR-019a` A production equilibrium-stage mode that changes liquid and vapor phase totals shall conserve component inventory and total tray energy during the phase update. A fixed-temperature/pressure phase target without latent-energy closure is diagnostic only.
- `FR-019b` A rigorously accepted hydraulic run shall have one thermodynamically consistent pressure owner. Hydraulic pressure, explicit vapor holdup, vapor volume, temperature, composition, and compressibility shall agree within an explicit closure tolerance.
- `FR-019c` In a rigorously accepted hydraulic run, internal liquid outflow shall be determined by active hydraulics from current state and geometry. Imported liquid-flow profiles may initialize or validate the model but shall not retain blended runtime ownership.
- `FR-019d` Vapor traffic and pressure closure shall be solved consistently with phase inventory and energy. Nominal-profile caps may be used as diagnosed startup safeguards but shall not determine the accepted operating profile.
- `FR-019e` The rigorous equilibrium-stage formulation shall use total component inventory and total internal energy as differential tray states. Temperature, pressure, phase split, phase compositions, and interstage liquid/vapor traffic shall be algebraic variables or outputs of the coupled closure.
- `FR-019f` The algebraic closure shall report local UV/component/energy/volume residuals separately from global pressure-drop and vapor-flow residuals. Passing local UV closure shall not imply passing global hydraulic closure.
- `FR-019g` Total condenser, reflux drum, partial reboiler, and bottoms sump representations shall have explicit conserved-state and volume mappings appropriate to their topology. A rigorous full-column closure shall not omit material or energy stored in terminal vapor or virtual terminal stages.
- `FR-019h` A rigorously accepted algebraic solution shall converge to materially the same state from pressure and flow guesses perturbed by at least `+/-10%`, unless a documented case-specific robustness range is stricter. Multiple materially different solutions or traversal-order dependence shall fail acceptance.
- `FR-019i` If frozen per-stage conserved totals and energies imply no physical global pressure/flow solution, the solver shall report the state as outside the algebraic constraint manifold. A subsequent steady-state solve may redistribute tray conserved states only while enforcing whole-column component and energy conservation and the specified operating degrees of freedom.
- `FR-019j` A conservative redistribution solver shall report per-node and aggregate `Delta N`, `Delta U`, pressure, and temperature movement from the reference checkpoint. Feasibility under conservation and ordering constraints shall not by itself constitute initializer acceptance; the accepted objective shall minimize scaled conserved-state movement and shall still pass global hydraulic and terminal closure.
- `FR-019k` A least-movement redistribution claim shall include materially different initial guesses, report convergence and objective value for every start, and require a reproducible accepted basin before hydraulic continuation. The gate shall also report terminal versus interior shares of absolute material and energy movement and shall reject a candidate whose apparent feasibility depends on large terminal reallocation or pressure discontinuity.
- `FR-019l` Before conserved-state redistribution is interpreted physically, the implementation shall audit `U=H-PV`, pressure-volume unit conversion, fixed-volume reconstruction, phase aggregation, eliminated-placeholder invariance, and objective scaling on all terminal owners plus representative interior controls. A node-local normalization that makes equal physical energy movement materially cheaper in terminal equipment shall be documented and corrected or explicitly justified before acceptance.
- `FR-019m` Conserved internal energy used by an initializer or steady-state solve shall be constructed on one canonical live-property basis. Any replacement of serialized phase enthalpy shall be reported separately from optimizer movement. A checkpoint-repair attempt shall predeclare its retry limit and acceptance gates; failure of the bounded corrected retry shall retire checkpoint projection and require a direct operating-specification steady-state formulation.
- `FR-019n` Before numerical solution, a direct steady-state formulation shall publish deterministic unknown and residual registries, deliberate eliminations, counts by block, closure ownership, a sparse dependency pattern, and a structural-rank audit. The registry shall be square, have no empty residual rows or unused unknown columns, and have no unexplained structural nullity. Separate terminal inventories may be combined into one conserved control volume only when the eliminated transfer is internal to that volume and all material, energy, phase, and level ownership remains explicit.
- `FR-019o` Before a direct nonlinear steady-state solve, every registered residual shall be evaluated with the selected live property backend at the primary guess and a deterministic physically bounded perturbation. The audit shall reject invalid reduced compositions without clipping or projection; prove component and energy telescoping independently; publish physical variable and residual scales; compute the scaled numerical Jacobian at two finite-difference step sizes; require full rank, no numerically unused unknown column, and stable rank at both guesses; and verify the registered sparsity pattern against an uncolored reference or equivalent independent check. A passing numerical gate authorizes bounded continuation only and is not initializer acceptance.
- `FR-019p` A staged direct steady-state continuation shall keep every active stage square, publish its released unknown and residual blocks, preserve the exact physical residual at the final homotopy endpoint, use smooth physical-domain coordinates, save accepted states, and stop on property failure, conservation loss, rank loss, excessive conditioning, coordinate saturation, or residual-gate failure. Full rank alone shall not establish endpoint feasibility. If a stage that fixes unreleased conserved component or energy states cannot reach physical closure under its predefined step and retry limits, the implementation shall revise the release ordering so conserved and phase states move consistently; it shall not lower tolerances, project the accepted state, or begin open-ended anchor tuning.
- `FR-019q` Every proposed continuation endpoint shall have full structural rank in its physical residual subgraph before a live solve. Anchor rows may establish a nonsingular lambda-zero homotopy but shall not conceal physical endpoint nullity. If the predefined final release-order redesign remains structurally singular, the system shall retire manual staged continuation; it shall not promote another equation family into a new first-stage variant. Subsequent work shall use a materially different architecture such as full-system pseudo-transient continuation, an analytic/automatic-derivative nonlinear or DAE solver, a reduced validation model, or an explicit physical-feasibility study.
- `FR-019r` Before full-system pseudo-transient development is authorized for a direct conserved formulation, one deterministic five-volume case shall retain the same live thermo, conserved component/energy, volume, equilibrium, Francis-hydraulic, vapor-pressure-drop, feed/product, terminal-equipment, and operating-specification equations. It shall publish structural and two-step numerical rank audits, use two predefined physical seeds, and attempt fixed trust-region and full-system pseudo-transient methods without clipping, profile forcing, equation-block removal, or post-result tuning. Authorization requires a common positive, pressure-ordered, conservative root with scaled physical residual `<1e-7`, full final rank, acceptable conditioning, no property fallback or coordinate saturation, and materially seed-independent results. Failure shall retire that formulation from production-initializer development; it shall not authorize a tray-count ladder, topology variation, tolerance change, solver sweep, or full-system pseudo-transient campaign.
- `FR-019s` A replacement rigorous architecture shall select one modeling family before implementation. The selected v2 family is equilibrium-stage DAE; a rate-based model with explicit interfacial mass- and heat-transfer laws is out of scope. Before code is written, v2 shall publish its physical control volumes, every crossing stream, differential and algebraic variable lists, one-owner table, complete governing equations, operating degrees of freedom, structural expectations, exclusions, phased validation gates, and stop rules.
- `FR-019t` The first v2 physical layer shall use prescribed ordered pressure, negligible tray vapor holdup, total component inventory and total internal energy differential states, algebraic temperature/compositions/equilibrium, Francis hydraulics as the sole tray liquid-flow owner, prescribed rectifying and stripping vapor rates, an algebraic total condenser, a liquid reflux drum, and one combined partial-reboiler/sump volume. The reduced steady specification shall own terminal liquid amounts and solve terminal product flows rather than leave terminal inventories free. It shall not contain equilibrium-relaxation transfer, profile-blended liquid flow, profile-capped or previous-step-owned vapor flow, controller-assisted acceptance, accepted projection, property fallback, or case-specific interior tray equations.
- `FR-019u` V2 shall pass gates in physical-complexity order: structural and source-equation assembly; one-volume energy/property closure; one five-inventory-volume prescribed-pressure column with prescribed section vapor rates and Francis-only tray liquid-flow ownership; one energy-determined vapor-traffic layer; unchanged production tray count; one simultaneous pressure-drop layer; and only then an optional explicit-vapor-inventory layer. A failed gate shall stop progression. It shall not trigger a tray-count ladder, tolerance change, solver sweep, or addition of a second physical owner.
- `FR-020` The model shall support optional top-drum PSV venting with linear gain and max-vent clamp.
- `FR-020a` In the standard explicit-sump configuration, the reboiler liquid feed shall be drawn from the bottom sump rather than directly from the bottom tray.
- `FR-020b` The runner shall support disabling separate top and bottom boundary states for validation sources whose stage set already includes the total condenser and reboiler.

### 4.5 Controls and Runtime Safeguards
- `FR-021` The runner shall support level PI control for top and bottom inventories.
- `FR-022` The runner shall support top-pressure PI control with MV selection (`top-anchor` or `condenser-duty`).
- `FR-023` The pressure loop shall support optional PV filtering, optional MV slew limiting, and residual-based gain attenuation.
- `FR-024` The runner shall support distillate composition PI control with reflux feasibility limiting.
- `FR-025` The runner shall support bottoms composition PI control with selectable MV (`boilup` or `reboiler-duty`).
- `FR-025a` Before a controlled rigorous solve, the system shall audit controller degrees of freedom. Each active controller shall have one available manipulated variable, and no manipulated variable shall have duplicate active ownership unless a documented selector or cascade structure resolves that ownership.
- `FR-026` The runner may use diagnosed clamps, projections, slew limits, and bound enforcement to protect startup or rejected nonlinear-solver trials.
- `FR-026a` A rigorously accepted algebraic or steady solution shall contain no negative phase amounts and shall not depend on an accepted state projection, binding imported-profile ceiling, previous-step limiter, or other safeguard that replaces the governing closure.
- `FR-026b` Solver reports shall distinguish rejected/attempted projections from projections present in an accepted iterate.
- `FR-031` The runner shall apply deterministic runtime-mode presets for pressure model, vapor-flow model, and liquid-hydraulic override according to selected `--runtime-mode`.

### 4.6 Logging and Ledger
- `FR-027` The system shall write profile and summary CSV logs when enabled.
- `FR-028` The system shall emit diagnostics for control commands, condenser/top-drum behavior, PSV behavior, and mass-closure signals.
- `FR-029` The CLI shall block duplicate exact command identities unless `--allow-repeat-command` is provided.
- `FR-030` The system shall append run registry metadata and regenerate `docs/experiment_ledger.csv` and `docs/experiment_ledger.md` after logged runs.
- `FR-032` Profile logs shall expose per-component dynamic-state K, thermo-equilibrium K, and their ratio (`K_state_*`, `K_thermo_*`, `K_state_over_K_thermo_*`).
- `FR-033` Bottoms-composition MV diagnostics shall reflect the selected MV mode: duty mode logs `Q_reb_cmd_BTUph`/`Q_reb_used_BTUph` as active MV and may leave `Boilup_cmd_lbmolph` undefined (`NaN`).
- `FR-034` The runner shall be able to export a restart workbook from a completed run, including optional `Boundary State`, `Energy State`, and `Controller State` sheets.
- `FR-035` A completed run shall be able to generate a human-readable Word report containing provenance, parameters, wall and simulation time, starting and ending conditions, controller and duty trends, and final stage profiles.
- `FR-036` A completed run shall be able to serialize and reload a native checkpoint containing the packed dynamic state and required runtime/controller memory. Reusable checkpoint artifacts shall pass a reload gate.
- `FR-037` Rigorous model acceptance shall include a physical-closure gate covering at least liquid-flow ownership, net phase/energy consistency, pressure versus vapor-holdup consistency, and non-binding diagnostic profile limits.
- `FR-037a` Unless superseded by a documented case requirement, rigorous local closure targets shall be: component reconstruction relative residual `<1e-8`; energy relative residual `<1e-7`; volume relative residual `<1e-7`; and phase-equilibrium fugacity residual or certified equivalent `<1e-6`. Global targets shall include scaled pressure-drop and vapor-flow residuals `<1e-5`, local-thermo versus global solved-pressure mismatch `<0.1 psi`, zero binding profile/previous-step flow limiters, zero accepted projections, complete terminal mapping, and the robustness requirement in `FR-019h`.

## 5. Traceability Matrix

| Requirement | Primary Implementation Trace | Test Trace |
|---|---|---|
| `UR-001`, `UR-002` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-003`, `FR-010`..`FR-014e` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/column_rhs_v1.py`, `src/dynamic_distillation/thermo_surrogate_v1.py`, `src/dynamic_distillation/thermo_table_pool_v1.py`, `src/dynamic_distillation/thermo_backend_factory_v1.py`, `src/dynamic_distillation/thermo_relative_volatility_provider_v1.py`, `tools/create_skogestad_column_a_validation_case.py`, `tools/compare_skogestad_column_a_profile.py`, `tools/compare_skogestad_dynamic_response.py`, `tools/plot_skogestad_dynamic_comparison.py`, `docs/cli.md`, `pyproject.toml` | `tests/test_stage_thermo_v1.py`, `tests/test_thermo_surrogate_v1.py`, `tests/test_thermo_table_pool_v1.py`, `tests/test_thermo_backend_factory_v1.py`, `tests/test_thermo_relative_volatility_provider_v1.py`, `tests/test_column_rhs_v1.py` |
| `UR-004`, `UR-013`, `FR-016`..`FR-020b` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/column_rhs_v1.py`, `src/dynamic_distillation/state_vector_layout_v1.py` | `tests/test_column_rhs_v1.py`, `tests/test_dynamic_run_scaffold_v1.py`, `tests/test_state_vector_layout_v1.py` |
| `UR-005`, `FR-021`..`FR-026`, `FR-031` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-006`, `FR-020` | `src/dynamic_distillation/column_rhs_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_column_rhs_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-007`, `FR-005` | `src/dynamic_distillation/excel_case_validator_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_excel_case_validator_v1.py` |
| `UR-008`, `FR-027`, `FR-028`, `FR-032`, `FR-033` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/column_rhs_v1.py` | `tests/test_dynamic_run_scaffold_v1.py`, `tests/test_column_rhs_v1.py` |
| `UR-009`, `FR-029` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/experiment_ledger_v1.py` | N/A |
| `UR-010`, `FR-030` | `src/dynamic_distillation/experiment_ledger_v1.py`, `tools/update_experiment_ledger.py` | N/A |
| `UR-012`, `FR-002a`, `FR-009a`, `FR-034` | `src/dynamic_distillation/excel_case_loader_v1.py`, `src/dynamic_distillation/column_spec_builder_v1.py`, `src/dynamic_distillation/state_vector_layout_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_excel_case_loader_v1.py`, `tests/test_column_spec_builder_v1.py`, `tests/test_state_vector_layout_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-011` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-014`, `FR-009b`, `FR-009c` | `docs/dynamic_column_initialization_strategy.md`, `docs/validation_readiness_gate_2026-05-26.md`, `docs/issue_log.md` (`DD-032`) | Planned; current support is documented policy plus residual/audit tooling under development. |
| `UR-015`..`UR-017`, `FR-007c`, `FR-009d`..`FR-009g`, `FR-019a`..`FR-019u`, `FR-025a`, `FR-026a`, `FR-026b`, `FR-037`, `FR-037a` | `docs/dynamic_model_current_state_2026-07-12.md`, `docs/dd_060_physics_owned_tray_flow_probe_20260712.md`, `docs/dd_065_frozen_checkpoint_uv_hydraulic_closure_20260717.md`, `docs/dd_066_terminal_conserved_inventory_mapping_20260717.md`, `docs/dd_067_conservative_energy_redistribution_probe_20260717.md`, `docs/dd_068_least_movement_redistribution_20260717.md`, `docs/dd_069_terminal_energy_volume_basis_audit_20260717.md`, `docs/dd_070_canonical_checkpoint_repair_20260717.md`, `docs/dd_071_direct_steady_state_registry_20260718.md`, `docs/dd_072_direct_steady_state_numerical_audit_20260718.md`, `docs/dd_073_direct_steady_state_continuation_20260718.md`, `docs/dd_074_merged_continuation_structural_audit_20260718.md`, `docs/dd_075_reduced_column_feasibility_20260718.md`, `docs/dd_076_equilibrium_dae_v2_architecture_contract_20260718.md`, `docs/dd_077_core_v2_structural_registry_20260718.md`, `docs/gates_explained.md`, `src/dynamic_distillation/direct_steady_state_registry_v1.py`, `src/dynamic_distillation/direct_steady_state_residual_v1.py`, `src/dynamic_distillation/direct_steady_state_continuation_v1.py`, `src/dynamic_distillation/reduced_column_feasibility_v1.py`, `src/dynamic_distillation/core_v2/reduced_topology_v1.py`, `src/dynamic_distillation/core_v2/reduced_column_spec_v1.py`, `src/dynamic_distillation/core_v2/reduced_state_registry_v1.py`, `src/dynamic_distillation/core_v2/reduced_residual_registry_v1.py`, `tools/audit_direct_steady_state_registry.py`, `tools/audit_direct_steady_state_numerics.py`, `tools/solve_direct_steady_state_continuation.py`, `tools/audit_merged_steady_state_continuation.py`, `tools/evaluate_reduced_column_feasibility.py`, `tools/audit_core_v2_reduced_registry.py` | DD-060 through DD-075 implementation tests preserve the retired-path evidence. DD-076 defines the replacement architecture. DD-077 passes its first `53 x 53` structural, ownership, and symbolic-conservation gate; `tests/test_core_v2_reduced_registry_v1.py` covers the new registry. Numerical residual evaluation and dynamic validation remain pending. |
| `FR-014f` | `src/dynamic_distillation/thermo_backend_factory_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `docs/issue_log.md` (`DD-059`) | Partial; Clapeyron fail-fast exists, DWSIM systematic-failure fail-fast remains open. |
| `FR-035` | `src/dynamic_distillation/run_report_v1.py`, `docs/run_reports.md` | `tests/test_run_report_v1.py` |
| `FR-036` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `tools/evaluate_initialization_dynamic_gate.py` | `tests/test_dynamic_run_scaffold_v1.py`, checkpoint reload-gate tests where available. |
| `FR-001`..`FR-004` | `src/dynamic_distillation/excel_case_loader_v1.py`, `src/dynamic_distillation/column_spec_builder_v1.py` | `tests/test_excel_case_loader_v1.py`, `tests/test_column_spec_builder_v1.py`, `tests/test_excel_case_validator_v1.py` |
| `FR-006`..`FR-009`, `FR-026` | `src/dynamic_distillation/state_vector_layout_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_state_vector_layout_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |

## 6. Notes and Limits
- This document is implementation-derived and intentionally reflects current behavior, not a future roadmap.
- Architecture requirements `FR-019a` through `FR-019u`, `FR-037`, and `FR-037a` were identified and refined by DD-060 through DD-077. DD-070 retires checkpoint repair. DD-071 and DD-072 establish full-system structural and numerical readiness. DD-073 stops at local closure, DD-074 retires manual staged continuation, and DD-075's structurally and numerically full-rank `71 x 71` reduced case fails both fixed trust-region and pseudo-transient methods. The present direct conserved formulation is therefore retired as a production initializer architecture, and full-system pseudo-transient work on it is not authorized. DD-076 selects the new equilibrium-DAE family. DD-077 passes the first isolated structural gate after correcting two free terminal inventory modes; numerical and dynamic validity remain unproven.
- `N/A` in tests indicates behavior exists in implementation without a dedicated direct unit/integration assertion at present.
