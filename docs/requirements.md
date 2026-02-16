# Dynamic Distillation Requirements

## 1. Document Control
- Title: Dynamic Distillation Requirements Specification
- Version: 1.0
- Date: 2026-02-15
- Source Basis: Current implementation and tests in this repository.

## 2. Scope
This document defines:
- User Requirements (`UR-*`): user-visible needs/capabilities.
- Functional Requirements (`FR-*`): system behavior and constraints.
- Traceability: links from each requirement to implementation and/or tests.

## 3. User Requirements
- `UR-001` The user shall be able to run a dynamic distillation simulation from an Excel case using CLI or Python API.
- `UR-002` The user shall be able to configure run horizon and integration controls (`n_steps`, `dt`, logging cadence).
- `UR-003` The user shall be able to choose thermo execution mode (`stub`, `dwsim`, `table`) and thermo refresh strategy.
- `UR-004` The user shall be able to override key operating boundary variables (reflux, boilup, condenser/reboiler duties, condenser pressure drop).
- `UR-005` The user shall be able to enable/disable closed-loop controls for level, top pressure, distillate composition, and bottoms composition.
- `UR-006` The user shall receive validation feedback before simulation execution, separated into blocking errors and non-blocking warnings.
- `UR-007` The user shall receive simulation outputs as structured logs (profile and summary CSV) when logging is enabled.
- `UR-008` The user shall be protected against accidental repeat execution of identical CLI experiments unless explicitly overridden.
- `UR-009` The user shall have automatic experiment provenance tracking (run registry and regenerated experiment ledger artifacts).

## 4. Functional Requirements

### 4.1 Case Loading and Normalization
- `FR-001` The system shall load case input from `.xlsx` and reject unsupported file types.
- `FR-002` The system shall parse specifications, initial conditions, and streams from expected template sheets.
- `FR-003` The system shall canonicalize Excel component names to DWSIM-compatible IDs before simulation build.

### 4.2 Model Build and Validation
- `FR-004` The system shall construct an immutable `ColumnSpec` from loaded case data.
- `FR-005` The system shall enforce stage-count and component-count consistency between specs and data tables.
- `FR-006` The system shall enforce ordered stage indexing (`1..N`) for initial conditions.
- `FR-007` The system shall validate required initial-condition columns and composition matrices.
- `FR-008` The system shall support optional geometry sections and derive per-stage geometry and vapor-volume arrays.
- `FR-009` The system shall provide a validation report with `errors`, `warnings`, and `ok` status.

### 4.3 State and RHS Computation
- `FR-010` The system shall define a deterministic state vector layout with optional vapor, top/bottom, temperature, and energy states.
- `FR-011` The system shall pack and unpack simulation states according to the active layout.
- `FR-012` The system shall compute ODE RHS derivatives and diagnostics for mass, optional energy, pressure, thermo, and hydraulics.
- `FR-013` The system shall support condenser duty modes `total-condense` and `specified`.
- `FR-014` The system shall support pressure models `spec` and `hydraulic`, including optional fixed condenser pressure drop.
- `FR-015` The system shall support thermo refresh throttling via cadence and optional threshold triggers (`dT`, `dP`, `dx`).
- `FR-016` The system shall support feed splitting at stage conditions via TP flash when provider capability is available.
- `FR-017` The system shall compute tray liquid outflow with Francis-weir hydraulics for internal trays and reject non-physical density input.

### 4.4 Thermodynamics Services
- `FR-018` The system shall provide provider-level TP flash services yielding `x`, `y`, `K`, and phase enthalpies.
- `FR-019` The system shall provide optional compressibility (`Z`) diagnostics when backend data is available.
- `FR-020` The system shall provide liquid density and Cp support for hydraulic and energy closures where available.
- `FR-021` The system shall fallback to alternate thermo backend path when primary DWSIM path is unavailable.

### 4.5 Runner and Control Execution
- `FR-022` The runner shall execute explicit Euler time integration for configured steps and timestep.
- `FR-023` The runner shall initialize vapor holdup to align startup diagnostic pressure with specified pressure profile.
- `FR-024` The runner shall clamp holdup states non-negative across integration updates.
- `FR-025` The runner shall clip temperature states to thermo-provider table bounds when such bounds are defined.
- `FR-026` The runner shall support control-loop updates for enabled control schemes and write commanded values to summary logging fields.
- `FR-027` The runner shall return a structured result object including paths, validation status, final state/time, and last diagnostics.

### 4.6 CLI, Logging, and Experiment Ledger
- `FR-028` The CLI shall expose runtime/model/control options, including backward-compatible aliases.
- `FR-029` The CLI shall detect exact duplicate commands from ledger identity and abort unless `--allow-repeat-command` is provided.
- `FR-030` The system shall write profile and summary CSVs when logging is enabled.
- `FR-031` The system shall append run metadata and exact command context to `logs/run_registry.csv`.
- `FR-032` The system shall regenerate `docs/experiment_ledger.csv` and `docs/experiment_ledger.md` from run artifacts.
- `FR-033` The ledger regeneration shall compute exact-command and suspected-result duplicate group indicators.

## 5. Traceability Matrix

| Requirement | Primary Implementation Trace | Test Trace |
|---|---|---|
| `UR-001` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:2640`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3593` | `tests/test_dynamic_run_scaffold_v1.py:30` |
| `UR-002` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:474`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3593` | `tests/test_dynamic_run_scaffold_v1.py:30` |
| `UR-003` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:655`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3593` | `tests/test_dynamic_run_scaffold_v1.py:227` |
| `UR-004` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:474`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:655` | `tests/test_dynamic_run_scaffold_v1.py:273` |
| `UR-005` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:1386`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:1507`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:1645`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:1763` | `tests/test_dynamic_run_scaffold_v1.py:123`, `tests/test_dynamic_run_scaffold_v1.py:227`, `tests/test_dynamic_run_scaffold_v1.py:354` |
| `UR-006` | `src/dynamic_distillation/excel_case_validator_v1.py:163`, `src/dynamic_distillation/excel_case_validator_v1.py:332` | `tests/test_excel_case_validator_v1.py:9` |
| `UR-007` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3569` | `tests/test_dynamic_run_scaffold_v1.py:123` |
| `UR-008` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3593`, `src/dynamic_distillation/experiment_ledger_v1.py:337` | N/A |
| `UR-009` | `src/dynamic_distillation/experiment_ledger_v1.py:503`, `src/dynamic_distillation/experiment_ledger_v1.py:568` | N/A |
| `FR-001` | `src/dynamic_distillation/excel_case_loader_v1.py:452` | `tests/test_excel_case_loader_v1.py:7` |
| `FR-002` | `src/dynamic_distillation/excel_case_loader_v1.py:357`, `src/dynamic_distillation/excel_case_loader_v1.py:452` | `tests/test_excel_case_loader_v1.py:7` |
| `FR-003` | `src/dynamic_distillation/excel_case_loader_v1.py:452`, `src/dynamic_distillation/compound_registry_v1.py:162` | `tests/test_compound_registry_v1.py:9` |
| `FR-004` | `src/dynamic_distillation/column_spec_builder_v1.py:166`, `src/dynamic_distillation/column_spec_builder_v1.py:332` | `tests/test_column_spec_builder_v1.py:5` |
| `FR-005` | `src/dynamic_distillation/column_spec_builder_v1.py:332` | `tests/test_excel_case_validator_v1.py:9` |
| `FR-006` | `src/dynamic_distillation/column_spec_builder_v1.py:332` | `tests/test_excel_case_validator_v1.py:9` |
| `FR-007` | `src/dynamic_distillation/column_spec_builder_v1.py:332` | `tests/test_excel_case_validator_v1.py:9` |
| `FR-008` | `src/dynamic_distillation/column_spec_builder_v1.py:216` | `tests/test_case_dump_geometry.py:150` |
| `FR-009` | `src/dynamic_distillation/excel_case_validator_v1.py:103`, `src/dynamic_distillation/excel_case_validator_v1.py:163` | `tests/test_excel_case_validator_v1.py:22` |
| `FR-010` | `src/dynamic_distillation/state_vector_layout_v1.py:128`, `src/dynamic_distillation/state_vector_layout_v1.py:152` | `tests/test_state_vector_layout_v1.py:29` |
| `FR-011` | `src/dynamic_distillation/state_vector_layout_v1.py:228` | `tests/test_state_vector_layout_v1.py:29` |
| `FR-012` | `src/dynamic_distillation/column_rhs_v1.py:322` | `tests/test_column_rhs_v1.py:59` |
| `FR-013` | `src/dynamic_distillation/column_rhs_v1.py:153` | `tests/test_column_rhs_v1.py:425`, `tests/test_column_rhs_v1.py:456` |
| `FR-014` | `src/dynamic_distillation/column_rhs_v1.py:153` | `tests/test_column_rhs_v1.py:1660` |
| `FR-015` | `src/dynamic_distillation/column_rhs_v1.py:153`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:655` | `tests/test_column_rhs_v1.py:1205`, `tests/test_column_rhs_v1.py:1284` |
| `FR-016` | `src/dynamic_distillation/column_rhs_v1.py:153` | `tests/test_column_rhs_v1.py:1011` |
| `FR-017` | `src/dynamic_distillation/stage_hydraulics_francis_v1.py:113` | `tests/test_column_rhs_v1.py:193` |
| `FR-018` | `src/dynamic_distillation/thermo_provider_v1.py:177`, `src/dynamic_distillation/stage_thermo_v1.py:144` | `tests/test_thermo_provider_v1.py:63`, `tests/test_stage_thermo_v1.py:24` |
| `FR-019` | `src/dynamic_distillation/pr_flash_backend_v1.py:726`, `src/dynamic_distillation/stage_thermo_v1.py:110` | `tests/test_stage_thermo_v1.py:49`, `tests/test_module8a_zfactor_pressure.py:52` |
| `FR-020` | `src/dynamic_distillation/thermo_provider_v1.py:234`, `src/dynamic_distillation/thermo_provider_v1.py:254` | `tests/test_pr_flash_backend_v1.py:51` |
| `FR-021` | `src/dynamic_distillation/pr_flash_backend_v1.py:726` | `tests/test_thermo_provider_v1.py:104` |
| `FR-022` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:2640` | `tests/test_dynamic_run_scaffold_v1.py:30` |
| `FR-023` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:2640` | `tests/test_dynamic_run_scaffold_v1.py:68` |
| `FR-024` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:1046` | `tests/test_dynamic_run_scaffold_v1.py:30` |
| `FR-025` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:1067` | `tests/test_dynamic_run_scaffold_v1.py:181` |
| `FR-026` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:2640` | `tests/test_dynamic_run_scaffold_v1.py:123`, `tests/test_dynamic_run_scaffold_v1.py:227`, `tests/test_dynamic_run_scaffold_v1.py:354` |
| `FR-027` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3569` | `tests/test_dynamic_run_scaffold_v1.py:30` |
| `FR-028` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3593` | N/A |
| `FR-029` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3593`, `src/dynamic_distillation/experiment_ledger_v1.py:337` | N/A |
| `FR-030` | `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3569` | `tests/test_dynamic_run_scaffold_v1.py:123` |
| `FR-031` | `src/dynamic_distillation/experiment_ledger_v1.py:503` | N/A |
| `FR-032` | `src/dynamic_distillation/experiment_ledger_v1.py:568` | N/A |
| `FR-033` | `src/dynamic_distillation/experiment_ledger_v1.py:416`, `src/dynamic_distillation/experiment_ledger_v1.py:442`, `src/dynamic_distillation/experiment_ledger_v1.py:568` | N/A |

## 6. Notes and Limits
- This requirements set is intentionally implementation-derived (current-state specification), not a forward-looking product roadmap.
- `N/A` in test trace means behavior is implemented but not directly covered by a dedicated test in the current suite.
