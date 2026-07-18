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
