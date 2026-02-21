# Dynamic Distillation Requirements

## 1. Document Control
- Title: Dynamic Distillation Requirements Specification
- Version: 1.1
- Date: 2026-02-17
- Basis: Current implementation and tests in this repository.

## 2. Scope
This specification captures the as-built behavior of the current codebase.

- `UR-*`: user-visible requirements.
- `FR-*`: functional/system requirements.
- Traceability links each requirement to implementation and test artifacts.

## 3. User Requirements
- `UR-001` Users shall be able to run dynamic distillation simulations from an Excel case through the Python CLI runner.
- `UR-002` Users shall be able to configure horizon and integration controls (`n_steps`, `dt`, logging cadence).
- `UR-003` Users shall be able to choose thermo execution mode (`stub`, `dwsim`, `table`, `table-pool`) and thermo refresh strategy.
- `UR-004` Users shall be able to override key operating variables (reflux, boilup, condenser/reboiler duties, condenser pressure drop).
- `UR-005` Users shall be able to enable/disable control loops for level, top pressure, distillate composition, and bottoms composition.
- `UR-006` Users shall be able to enable top-drum PSV relief behavior and configure setpoint/gain/max vent.
- `UR-007` Users shall receive startup validation feedback split into blocking errors and non-blocking warnings.
- `UR-008` Users shall receive structured profile/summary CSV outputs when logging is enabled.
- `UR-009` Users shall be protected against accidental reruns of identical CLI commands unless explicitly overridden.
- `UR-010` Users shall have automatic run provenance tracking and experiment-ledger regeneration.

## 4. Functional Requirements

### 4.1 Case Loading and Validation
- `FR-001` The system shall load `.xlsx` case files and reject unsupported file types.
- `FR-002` The loader shall parse `Specifications`, `Initial Conditions`, and (best-effort) `Streams`.
- `FR-003` The loader shall canonicalize Excel component names to DWSIM-compatible component IDs.
- `FR-004` The system shall build a validated `ColumnSpec` and enforce stage/component consistency.
- `FR-005` The runner shall perform preflight validation and stop before integration on blocking errors.

### 4.2 State Initialization and Startup Conditioning
- `FR-006` The runner shall construct deterministic state layout and initial state vector from `ColumnSpec`.
- `FR-007` The runner shall initialize tray vapor holdup to match startup pressure profile assumptions.
- `FR-008` The runner shall support optional startup thermo-consistent conditioning iterations.
- `FR-009` The runner shall perform top-drum startup steadying pass for top-holdup residual reduction when top states are active.

### 4.3 Thermodynamics Services
- `FR-010` The system shall support thermo providers for TP flash, phase enthalpy, and optional Z-factor diagnostics.
- `FR-011` The system shall support tabular thermo from JSON surrogate tables.
- `FR-012` The system shall support process-pool tabular thermo mode for parallel batched stage flashes.
- `FR-013` The RHS shall use provider batch flash when available and fall back to scalar flash otherwise.
- `FR-014` The system shall support thermo refresh throttling by step cadence and optional per-stage `dT/dP/dx` thresholds.

### 4.4 RHS, Physics, and Closures
- `FR-015` The RHS shall compute tray/top/bottom component holdup derivatives with feed and boundary source terms.
- `FR-016` The model shall support condenser duty modes `total-condense` and `specified`.
- `FR-017` The model shall support pressure models `spec` and `hydraulic`, including optional condenser pressure drop.
- `FR-018` The model shall support vapor-flow models `profile` and `energy` with reboiler-neighbor vapor guardrails.
- `FR-019` The model shall support optional equilibrium relaxation and optional energy-holdup states.
- `FR-020` The model shall support optional top-drum PSV venting with linear gain and max-vent clamp.

### 4.5 Controls and Runtime Safeguards
- `FR-021` The runner shall support level PI control for top and bottom inventories.
- `FR-022` The runner shall support top-pressure PI control with MV selection (`top-anchor` or `condenser-duty`).
- `FR-023` The pressure loop shall support optional PV filtering, optional MV slew limiting, and residual-based gain attenuation.
- `FR-024` The runner shall support distillate composition PI control with reflux feasibility limiting.
- `FR-025` The runner shall support bottoms composition PI control with selectable MV (`boilup` or `reboiler-duty`).
- `FR-026` The runner shall clamp non-physical states (e.g., nonnegative holdup enforcement, temperature clipping to provider bounds).

### 4.6 Logging and Ledger
- `FR-027` The system shall write profile and summary CSV logs when enabled.
- `FR-028` The system shall emit diagnostics for control commands, condenser/top-drum behavior, PSV behavior, and mass-closure signals.
- `FR-029` The CLI shall block duplicate exact command identities unless `--allow-repeat-command` is provided.
- `FR-030` The system shall append run registry metadata and regenerate `docs/experiment_ledger.csv` and `docs/experiment_ledger.md` after logged runs.

## 5. Traceability Matrix

| Requirement | Primary Implementation Trace | Test Trace |
|---|---|---|
| `UR-001`, `UR-002` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-003`, `FR-010`..`FR-014` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/column_rhs_v1.py`, `src/dynamic_distillation/thermo_surrogate_v1.py`, `src/dynamic_distillation/thermo_table_pool_v1.py` | `tests/test_stage_thermo_v1.py`, `tests/test_thermo_surrogate_v1.py`, `tests/test_thermo_table_pool_v1.py`, `tests/test_column_rhs_v1.py` |
| `UR-004`, `FR-016`..`FR-019` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/column_rhs_v1.py` | `tests/test_column_rhs_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-005`, `FR-021`..`FR-025` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-006`, `FR-020` | `src/dynamic_distillation/column_rhs_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_column_rhs_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-007`, `FR-005` | `src/dynamic_distillation/excel_case_validator_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_excel_case_validator_v1.py` |
| `UR-008`, `FR-027`, `FR-028` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_dynamic_run_scaffold_v1.py` |
| `UR-009`, `FR-029` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py`, `src/dynamic_distillation/experiment_ledger_v1.py` | N/A |
| `UR-010`, `FR-030` | `src/dynamic_distillation/experiment_ledger_v1.py`, `tools/update_experiment_ledger.py` | N/A |
| `FR-001`..`FR-004` | `src/dynamic_distillation/excel_case_loader_v1.py`, `src/dynamic_distillation/column_spec_builder_v1.py` | `tests/test_excel_case_loader_v1.py`, `tests/test_column_spec_builder_v1.py`, `tests/test_excel_case_validator_v1.py` |
| `FR-006`..`FR-009`, `FR-026` | `src/dynamic_distillation/state_vector_layout_v1.py`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py` | `tests/test_state_vector_layout_v1.py`, `tests/test_dynamic_run_scaffold_v1.py` |

## 6. Notes and Limits
- This document is implementation-derived and intentionally reflects current behavior, not a future roadmap.
- `N/A` in tests indicates behavior exists in implementation without a dedicated direct unit/integration assertion at present.
