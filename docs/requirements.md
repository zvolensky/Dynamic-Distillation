# Dynamic Distillation Requirements

## 1. Document Control
- Title: Dynamic Distillation Requirements Specification
- Version: 1.5
- Date: 2026-07-12
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

This system implements an explicit-vapor, rigorous-energy column model that produces a **stiff, Index-1+ DAE (Differential-Algebraic Equation)** with coupled pressure, holdup, composition, temperature, and hydraulic states. Unlike simplified textbook treatments that assume Constant Molar Overflow and implicit hydraulics, this model's equations directly couple differential states (like vapor moles in fixed shell volumes) to algebraic constraints (like vapor flow rates and pressure drops).

From the published literature on DAE initialization (Pantelides 1988; Barton, Biegler), a steady-state profile from an external tool (ChemSep, Aspen Plus, DWSIM) satisfies only the static mass and energy balances at $t=0$. It **does not** satisfy the dynamic hydraulic equations, vapor-pipe resistances, weir crest heights, or thermal sub-cooling profiles that the dynamic RHS requires. When the integrator evaluates the right-hand side at $t=0$, it computes large, non-zero derivatives, causing computational impulse shocks.

The Consistent Initialization Solver must therefore:
1. Hold specified independent variables fixed (feed rate, geometry).
2. Vary targeted initial states to drive all time derivatives simultaneously to zero at $t=0$.
3. Verify block-level and global conservation/closure simultaneously.

Initialization is not a trivial "switch to dynamics" operation; it is a distinct mathematical problem requiring structured root-finding, conservation audits, and acceptance gating. See `docs/dynamic_column_initialization_strategy.md` for mathematical foundation and workflow.

Requirements in this section define how external seeds are loaded, how initialization passes condition the column toward dynamic self-consistency, and what acceptance gates must pass before integration begins.


- `FR-006` The runner shall construct deterministic state layout and initial state vector from `ColumnSpec`.
- `FR-007` The runner shall initialize tray vapor holdup to match startup pressure profile assumptions.
- `FR-007a` When `--use-excel-vapor-holdup` is enabled, the runner shall preserve explicit tray vapor holdup from the Excel `Initial Conditions` sheet through startup pressure initialization and thermo conditioning.
- `FR-007b` The runner shall support disabling dynamic tray vapor states for validation sources whose vapor composition is algebraic and whose equations do not include vapor holdup ODEs.
- `FR-008` The runner shall support optional startup thermo-consistent conditioning iterations.
- `FR-009` The runner shall perform top-drum startup steadying pass for top-holdup residual reduction when top states are active.
- `FR-009a` When explicit runtime restart state is present, the runner shall skip vapor reseeding and startup conditioning/steadying steps that would overwrite the restart state.
- `FR-009b` External steady-state profiles, including ChemSep-derived profiles, shall be treated as initialization seeds unless a model-consistent residual audit or initializer demonstrates that the state is steady under this model's active topology, thermo, feed treatment, holdup states, and RHS equations.
- `FR-009c` Accepted dynamic initialization shall require block-level derivative/conservation checks in addition to any aggregate steady-state detector flag.
- `FR-009d` Initializer acceptance shall be conditional on a model-physics closure gate. An initializer shall not be expected to create a rigorous zero-residual state when the active runtime equations assign competing owners to pressure, phase totals, energy, or interstage flow.
- `FR-009e` Runtime steady-state acceptance shall include a whole-column inventory-rate criterion in addition to local state-rate criteria. A run with material `F-D-B` drift shall not pass solely because the drift is distributed across many tray states.

### 4.3 Thermodynamics Services
- `FR-010` The system shall support thermo providers for TP flash, phase enthalpy, and optional Z-factor diagnostics.
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
- `FR-020` The model shall support optional top-drum PSV venting with linear gain and max-vent clamp.
- `FR-020a` In the standard explicit-sump configuration, the reboiler liquid feed shall be drawn from the bottom sump rather than directly from the bottom tray.
- `FR-020b` The runner shall support disabling separate top and bottom boundary states for validation sources whose stage set already includes the total condenser and reboiler.

### 4.5 Controls and Runtime Safeguards
- `FR-021` The runner shall support level PI control for top and bottom inventories.
- `FR-022` The runner shall support top-pressure PI control with MV selection (`top-anchor` or `condenser-duty`).
- `FR-023` The pressure loop shall support optional PV filtering, optional MV slew limiting, and residual-based gain attenuation.
- `FR-024` The runner shall support distillate composition PI control with reflux feasibility limiting.
- `FR-025` The runner shall support bottoms composition PI control with selectable MV (`boilup` or `reboiler-duty`).
- `FR-026` The runner shall clamp non-physical states (e.g., nonnegative holdup enforcement, temperature clipping to provider bounds).
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
| `UR-015`, `FR-009d`, `FR-019a`..`FR-019d`, `FR-037` | `docs/dynamic_model_current_state_2026-07-12.md`, `docs/dd_060_physics_owned_tray_flow_probe_20260712.md`, `docs/gates_explained.md`, `src/dynamic_distillation/uv_flash_stage_v1.py` | Open architecture requirement; DD-060 is diagnostic evidence, not a passing implementation. |
| `FR-014f` | `src/dynamic_distillation/thermo_backend_factory_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `docs/issue_log.md` (`DD-059`) | Partial; Clapeyron fail-fast exists, DWSIM systematic-failure fail-fast remains open. |
| `FR-035` | `src/dynamic_distillation/run_report_v1.py`, `docs/run_reports.md` | `tests/test_run_report_v1.py` |
| `FR-036` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `tools/evaluate_initialization_dynamic_gate.py` | `tests/test_dynamic_run_scaffold_v1.py`, checkpoint reload-gate tests where available. |
| `FR-001`..`FR-004` | `src/dynamic_distillation/excel_case_loader_v1.py`, `src/dynamic_distillation/column_spec_builder_v1.py` | `tests/test_excel_case_loader_v1.py`, `tests/test_column_spec_builder_v1.py`, `tests/test_excel_case_validator_v1.py` |
| `FR-006`..`FR-009`, `FR-026` | `src/dynamic_distillation/state_vector_layout_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_state_vector_layout_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |

## 6. Notes and Limits
- This document is implementation-derived and intentionally reflects current behavior, not a future roadmap.
- `FR-019a` through `FR-019d` and `FR-037` are open acceptance requirements identified by DD-060. The current DD-058 checkpoint does not satisfy them and is classified as an operational baseline rather than a rigorous physical validation.
- `N/A` in tests indicates behavior exists in implementation without a dedicated direct unit/integration assertion at present.
