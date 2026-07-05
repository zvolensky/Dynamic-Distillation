# Dynamic Distillation Model Architecture

This document describes the current architecture of the dynamic distillation model in this repository.
It is intended as an implementation-level reference for model behavior, coupling, and runtime execution.

For project terminology, see `docs/glossary.md`.

## Design Complexity and Initialization Implications

This model differs fundamentally from simplified textbook treatments of distillation. Rather than employing **Constant Molar Overflow (CMO)** assumptions and implicit hydraulics, the column uses:

- **Explicit vapor volume** with physical rigidity constraints (fixed shell volumes)
- **Rigorous energy topology** with temperature and enthalpy states on trays and boundary vessels
- **Coupled hydraulic-pressure closure** where pressure is a differential state computed from vapor-phase accumulation

This rigorous formulation aligns with published DAE (Differential-Algebraic Equation) literature and matches the hidden mathematical structure of commercial dynamic simulators like Aspen Dynamics. However, it creates a **stiff, Index-1+ DAE system** where microscopic inconsistencies at $t=0$ can produce violent computational shocks.

In consequence, initialization is not a trivial "switch to dynamics" operation. The model requires a **Consistent Initialization Solver**—described in detail in `docs/dynamic_column_initialization_strategy.md`—to ensure all time derivatives are simultaneously driven to zero at $t=0$ before integration begins.

See `docs/dynamic_column_initialization_strategy.md` for the mathematical foundation and practical workflow.
See `docs/initialization_code_status.md` for the current support status of initialization, reconciliation, and startup-homotopy tooling.

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
- Startup initialization quality strongly affects early transient stiffness.

## 12) Future Architecture Options

Larger refactor option:
- move to a broader implicit simultaneous solve (DAE/NL system across pressure, vapor flow, energy, and phase terms).
