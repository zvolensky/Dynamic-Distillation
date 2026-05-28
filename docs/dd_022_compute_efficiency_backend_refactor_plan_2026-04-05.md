# Compute-Efficiency Refactor Plan

Date: 2026-04-05

Branch target: `refactor/compute-efficiency`

Primary input: `docs/dd_021_live_thermo_efficiency_report_2026-04-05.md`

## Intent

Pursue the next major efficiency step identified in the April 5 report by combining two changes:

1. reduce duplicated thermo work inside each RHS step
2. make the live-thermo backend pluggable, with the first new target aimed at a Clapeyron-backed integration path and later adapters for `ThermoPack` and `thermo`

This plan assumes the backend architecture matters at least as much as raw backend speed. The report already showed that DWSIM property-package swaps alone do not solve the runtime problem.

## Working Assumptions

- The current best short hydraulic benchmark is the April 4 water-methanol run `20260404_162348`, with the dominant buckets:
  - `main_tray_refresh`
  - `energy_vapor_flow_enthalpy_refresh`
  - `temperature_state_cp_lookup`
- The current repo already has useful seams we should preserve:
  - provider construction is centralized in `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
  - provider calls are normalized through `src/dynamic_distillation/stage_thermo_v1.py`
  - `src/dynamic_distillation/column_rhs_v1.py` already supports optional `flash_TP_full_batch(...)`
  - table and table-pool providers already demonstrate a provider family with shared scalar semantics and optional batch support
- We should not hard-code a Clapeyron-specific shape into the RHS. The RHS should depend on capabilities and packets, not on one backend's transport or API.
- "Clapeyron.js" is treated here as a Clapeyron-targeted backend path. The transport should be isolated enough that the concrete implementation can be either a direct Python bridge or an external sidecar without forcing another RHS rewrite.

## Refactor Goals

## Primary goals

- Cut duplicated live thermo evaluations inside one RHS step.
- Replace ad hoc provider expectations with an explicit backend capability contract.
- Introduce a shared thermo packet for one step so `main_tray_refresh`, vapor enthalpy refresh, temperature-state enthalpy refresh, and helper flashes can reuse common results.
- Add a new non-DWSIM live backend slot with Clapeyron targeted first.
- Keep the design open for `ThermoPack` and `thermo`.

## Non-goals for the first pass

- Do not rewrite the whole simulator into a fully simultaneous DAE solve.
- Do not remove the existing DWSIM, table, or table-pool paths.
- Do not try to solve surrogate trustworthiness in the same change set.
- Do not optimize helper thresholds further until the shared packet path exists.

## Success Criteria

## Functional

- Existing `dwsim`, `table`, `table-pool`, and `stub` modes still run.
- Existing tests for thermo provider behavior, stage thermo normalization, and runner thermo-mode selection still pass after adaptation.
- New provider modes can be selected without changing RHS logic.

## Architectural

- RHS depends on one shared thermo coordinator rather than issuing overlapping flash and Cp calls from multiple blocks.
- Provider-specific transport code lives outside `column_rhs_v1.py`.
- Batch capability is exposed through a formal interface instead of duck-typed one-off assumptions.

## Performance

- First internal milestone: reduce combined `main_tray_refresh` plus `energy_vapor_flow_enthalpy_refresh` direct flashes by at least 40% on the short water-methanol hydraulic benchmark.
- First internal milestone: reduce `temperature_state_cp_lookup` backend-equivalent count by at least 50% on the same benchmark.
- Second milestone: reach a 2x wall-time improvement over the current best short live benchmark, either through architecture alone or architecture plus the first alternate backend.

These are working targets, not release promises. The report already showed that lower flash counts do not guarantee lower wall time unless the slowest work is removed from the critical path.

## Proposed Architecture

## 1. Split "provider" into contract, adapter, and backend

Introduce a small thermo contract layer that the RHS can trust regardless of backend:

- `ThermoBackendCapabilities`
  - `supports_batch_tp_flash`
  - `supports_direct_cp`
  - `supports_phase_enthalpy`
  - `supports_bubble_point`
  - `supports_density`
  - `supports_z_factor`
  - `supports_stage_context`
  - `supports_session_reuse`
- `ThermoFlashRequest`
  - stage index
  - temperature
  - pressure
  - overall composition
  - category tag
- `ThermoFlashResult`
  - `x`, `y`, `K`, `HL`, `HV`, optional `Z`
  - optional `cpL`, `cpV`
  - provider metadata for debugging and counter attribution
- `ThermoBackendAdapter`
  - scalar flash
  - optional batch flash
  - optional direct Cp
  - optional phase enthalpy
  - optional density
  - optional bubble-point solve
  - debug tracing / counter snapshot / reset

This is a stronger version of the current implicit contract shared by:

- `ThermoProviderV1`
- `TabularThermoProviderV1`
- `ParallelTabularThermoProviderV1`

## 2. Add a step-scoped thermo coordinator

Create a new step-scoped object that owns all thermo work for one RHS call:

- proposed module: `src/dynamic_distillation/thermo_step_coordinator_v1.py`

Core responsibilities:

- accept tray states requested by RHS sub-blocks
- deduplicate requests by stage plus compatible state
- batch the refresh when backend supports batching
- return one `TrayThermoPacket` with all available data
- expose helper-level caches for condenser and reboiler support calls
- record category-level call accounting without losing current trace visibility

This is the core architectural move from the report. The coordinator should make it hard for `main_tray_refresh` and `energy_vapor_flow_enthalpy_refresh` to solve nearly the same state twice.

## 3. Promote `TrayThermoPacket` from cache artifact to authoritative step result

`TrayThermoPacket` already exists in `column_rhs_v1.py`, but it is mainly used as a reuse container. It should become the main thermo data exchange object.

Expand it carefully to carry:

- tray-state `T` and `P`
- overall `z`
- equilibrium `x` and `y`
- `K`, `HL`, `HV`, `Z`
- optional `cpL`, `cpV`
- source flags:
  - fresh flash
  - reused prior-step packet
  - derived Cp from packet slope
  - helper-reused
  - fallback-computed
- validity windows:
  - max `dT`
  - max `dP`
  - max `dz`

The packet should be rich enough that temperature-state and helper logic can ask "can I reuse?" without each call path reinventing its own heuristic.

## 4. Support both in-process and sidecar backends

Use one provider factory that can build either:

- in-process adapters
  - DWSIM
  - table
  - table-pool
  - `ThermoPack`
  - `thermo`
- sidecar-backed adapters
  - Clapeyron target
  - future isolated DWSIM or other compiled backends if needed

The transport boundary should sit below the adapter contract, not above the whole RHS.

Recommended initial transport split:

- `LocalThermoBackendAdapter`: wraps Python-callable backends directly
- `RemoteThermoBackendAdapter`: wraps a persistent sidecar session with batch request methods

That keeps `ThermoPack` and `thermo` simple while still giving Clapeyron a realistic path whether we use a direct Python bridge first or a sidecar session.

## Phase Plan

## Phase 0. Baseline freeze and guardrails

Purpose: protect current behavior before the refactor starts.

Work:

- Add a benchmark harness script for the report's key checkpoints:
  - water-methanol short hydraulic probe
  - water-methanol capped 5-minute hydraulic probe
  - depropanizer short hydraulic probe
- Save a machine-readable benchmark manifest in `docs/` or `tools/`.
- Add one test helper for comparing thermo counter snapshots before and after a run.
- Capture the current short-benchmark counters as reference fixtures in a lightweight JSON file.

Likely files:

- new `tools/bench_live_thermo_refactor_v1.py`
- new benchmark manifest JSON under `docs/` or `tools/`
- small test additions in `tests/test_dynamic_run_scaffold_v1.py`

Exit criteria:

- We can rerun the benchmark set with one command.
- We have a stable before/after measurement harness for flash counts and wall time.

## Phase 1. Formalize the backend contract

Purpose: stop embedding backend-specific expectations directly in runner and RHS.

Work:

- Add a new contract module, for example:
  - `src/dynamic_distillation/thermo_backend_protocol_v1.py`
- Define capability and result dataclasses.
- Add adapter wrappers for existing providers:
  - DWSIM current provider
  - table
  - table-pool
  - stub
- Add a provider factory module, for example:
  - `src/dynamic_distillation/thermo_backend_factory_v1.py`
- Update `build_inputs_for_runner(...)` so it uses the factory instead of directly branching over provider classes.

Likely files:

- new `src/dynamic_distillation/thermo_backend_protocol_v1.py`
- new `src/dynamic_distillation/thermo_backend_factory_v1.py`
- update `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- update `tests/test_dynamic_run_scaffold_v1.py`
- update `tests/test_thermo_provider_v1.py`

Exit criteria:

- Existing modes still construct through one factory.
- Existing tests pass with the adapter layer in place.
- RHS still runs unchanged at this phase.

## Phase 2. Move step thermo work behind a coordinator

Purpose: eliminate duplicate thermo solves within one RHS call.

Work:

- Add `thermo_step_coordinator_v1.py`.
- Move refresh scheduling and packet assembly out of the middle of `column_rhs_v1.py`.
- Create APIs such as:
  - `prepare_main_stage_packet(...)`
  - `ensure_vapor_enthalpy_for_stages(...)`
  - `ensure_temperature_state_properties(...)`
  - `get_condenser_duty_packet(...)`
  - `get_reboiler_helper_packet(...)`
- Ensure the coordinator can:
  - merge tray requests from multiple call sites
  - perform one batch refresh when possible
  - record which values came from a shared flash versus secondary fallback work
- Keep the current category accounting, but route it through coordinator-owned request categories.

Likely files:

- new `src/dynamic_distillation/thermo_step_coordinator_v1.py`
- update `src/dynamic_distillation/column_rhs_v1.py`
- update `tests/test_column_rhs_v1.py`

Exit criteria:

- `column_rhs_v1.py` no longer owns the bulk of flash orchestration logic directly.
- The short DWSIM hydraulic benchmark shows a real drop in duplicated flash categories.

## Phase 3. Collapse `main_tray_refresh` and `energy_vapor_flow_enthalpy_refresh`

Purpose: attack the two biggest buckets first.

Work:

- Replace the current two-path refresh behavior with one staged refresh plan:
  - determine which trays need fresh thermo
  - flash those trays once
  - populate both tray equilibrium data and vapor enthalpy data from the same results
- Extend `TrayThermoPacket` so vapor enthalpy consumers can trust packet freshness and provenance.
- Remove secondary enthalpy refresh calls where the packet already carries valid `HV`.
- Keep a narrow fallback for cases where a backend returns incomplete fields.

Likely files:

- update `src/dynamic_distillation/column_rhs_v1.py`
- update `src/dynamic_distillation/stage_thermo_v1.py`
- update `tests/test_column_rhs_v1.py`

Exit criteria:

- The benchmark no longer reports separate large buckets for main tray refresh and vapor-flow enthalpy refresh on the same stage set.
- Same-step vapor enthalpy reuse becomes the default path, not a special-case optimization.

## Phase 4. Refactor Cp handling around packet-first logic

Purpose: remove the remaining large `temperature_state_cp_lookup` backend-equivalent burden.

Work:

- Make packet-derived Cp the primary path where the local state movement is within validity limits.
- Add backend contract hooks for direct Cp only as a fallback path.
- Introduce packet-level derivative caches or enthalpy-slope snapshots when available.
- Move Cp policy into one module so `column_rhs_v1.py` does not own multiple overlapping fallback ladders.
- Add explicit trace fields to distinguish:
  - packet-derived Cp
  - direct-backend Cp
  - finite-difference fallback Cp

Likely files:

- new helper module if needed, for example `thermo_cp_policy_v1.py`
- update `src/dynamic_distillation/column_rhs_v1.py`
- update `src/dynamic_distillation/thermo_provider_v1.py`
- update tests in `tests/test_column_rhs_v1.py` and `tests/test_thermo_provider_v1.py`

Exit criteria:

- `temperature_state_cp_lookup` backend-equivalent counts fall materially on the benchmark run.
- Cp behavior remains traceable and testable.

## Phase 5. Add the Clapeyron-targeted backend path

Purpose: create the first new live backend without coupling the repo to one transport choice.

Recommended implementation shape:

- keep the simulator side Python
- keep the Clapeyron adapter transport-isolated from the start
- begin with the fastest viable spike:
  - direct Python bridge if `pyclapeyron` covers the needed calls cleanly
  - otherwise a persistent sidecar adapter
- support at least:
  - single TP flash
  - batch TP flash
  - direct phase enthalpy or enthalpy from flash result
  - optional Cp and bubble-point helpers

Why a sidecar-ready boundary is still important even if a direct bridge works:

- it avoids embedding one runtime strategy throughout the repo
- it gives a natural place for session reuse and batching
- it creates the same seam we can later reuse for other isolated backends

Suggested minimum service contract:

- `initialize_session`
- `flash_tp`
- `flash_tp_batch`
- `phase_enthalpy`
- `cp`
- `bubble_point`
- `liquid_density`
- `component_mw`
- `health`
- `shutdown`

Suggested repo structure:

- `src/dynamic_distillation/backends/clapeyron_adapter_v1.py`
- `src/dynamic_distillation/backends/remote_backend_client_v1.py`
- sidecar code in a sibling folder such as:
  - `external/clapeyron_sidecar/`
  - or `tools/clapeyron_sidecar/`

Acceptance strategy:

- start with water-methanol parity flash parity checks against current DWSIM/table expectations
- then benchmark micro flash batches
- then run the short hydraulic benchmark

Exit criteria:

- `thermo_mode=clapeyron` or equivalent factory key works end to end for at least one benchmark case
- batch path is functional
- failures degrade clearly instead of silently corrupting state

## Phase 6. Add `ThermoPack` and `thermo` adapters

Purpose: validate that the abstraction is genuinely backend-flexible.

Implementation order:

1. `thermo`
2. `ThermoPack`

Reason:

- `thermo` is likely easiest to stand up inside Python and is useful for adapter shakeout
- `ThermoPack` is the stronger compiled candidate, but its integration cost is higher

Recommended shape:

- `src/dynamic_distillation/backends/thermo_python_adapter_v1.py`
- `src/dynamic_distillation/backends/thermopack_adapter_v1.py`

Acceptance:

- each adapter can run the same conformance tests
- each adapter publishes capability flags honestly
- the runner uses the same factory and RHS coordinator unchanged

Exit criteria:

- at least one additional non-DWSIM adapter works through the same contract
- no backend-specific branching leaks back into `column_rhs_v1.py`

## Phase 7. Re-benchmark and tune refresh policy by backend

Purpose: separate architecture gains from backend gains.

Work:

- rerun the same benchmark set on:
  - DWSIM after refactor
  - Clapeyron-targeted backend
  - `thermo`
  - `ThermoPack` when available
- compare:
  - wall time
  - direct flash count
  - backend-equivalent count
  - batch size utilization
  - helper-fallback frequency
- tune backend-specific refresh tolerances only after the shared packet path is stable

Deliverable:

- follow-up report in `docs/` with before/after architecture and backend comparisons

## Concrete File Map

## Existing files likely to change

- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- `src/dynamic_distillation/column_rhs_v1.py`
- `src/dynamic_distillation/stage_thermo_v1.py`
- `src/dynamic_distillation/thermo_provider_v1.py`
- `src/dynamic_distillation/thermo_surrogate_v1.py`
- `src/dynamic_distillation/thermo_table_pool_v1.py`
- `tests/test_dynamic_run_scaffold_v1.py`
- `tests/test_column_rhs_v1.py`
- `tests/test_thermo_provider_v1.py`
- `tests/test_stage_thermo_v1.py`

## New files recommended

- `src/dynamic_distillation/thermo_backend_protocol_v1.py`
- `src/dynamic_distillation/thermo_backend_factory_v1.py`
- `src/dynamic_distillation/thermo_step_coordinator_v1.py`
- `src/dynamic_distillation/backends/clapeyron_adapter_v1.py`
- `src/dynamic_distillation/backends/remote_backend_client_v1.py`
- `src/dynamic_distillation/backends/thermo_python_adapter_v1.py`
- `src/dynamic_distillation/backends/thermopack_adapter_v1.py`
- `tools/bench_live_thermo_refactor_v1.py`
- `tests/test_thermo_backend_factory_v1.py`
- `tests/test_thermo_step_coordinator_v1.py`
- `tests/test_backend_conformance_v1.py`

## Testing Strategy

## 1. Conformance tests

One shared backend test matrix should verify:

- scalar flash result shape
- optional batch flash result shape
- Cp availability behavior
- bubble-point behavior
- density behavior
- trace context forwarding
- counter snapshot/reset behavior

Each adapter should pass the same base suite, with capability-conditional assertions where appropriate.

## 2. RHS behavior tests

Focus on:

- shared packet reuse across main tray and vapor enthalpy logic
- Cp packet reuse and fallback paths
- helper packet reuse for condenser and reboiler support
- batch versus scalar refresh parity

## 3. End-to-end tests

Run small deterministic cases for:

- `stub`
- `table`
- `table-pool`
- `dwsim`
- first alternate backend as soon as available

## 4. Benchmark tests

Treat these as required before merging major phases:

- water-methanol short hydraulic benchmark
- water-methanol capped longer hydraulic probe
- depropanizer short hydraulic probe

## Execution Order Recommendation

Use this order to keep the repo runnable throughout the refactor:

1. Phase 0 baseline harness
2. Phase 1 contract plus factory
3. Phase 2 coordinator scaffold with DWSIM still underneath
4. Phase 3 main flash plus vapor enthalpy collapse
5. Phase 4 Cp refactor
6. Phase 5 Clapeyron-targeted backend
7. Phase 6 `thermo`
8. Phase 6 `ThermoPack`
9. Phase 7 benchmark report and tuning

This order keeps the architecture work ahead of backend exploration, which is important because the report suggests call-count architecture is still the main bottleneck.

## Risks And Mitigations

## Risk: abstraction slows the hot path

Mitigation:

- keep dataclasses lightweight
- avoid repeated conversion between Python lists and arrays
- batch requests at the coordinator boundary

## Risk: Clapeyron bridge overhead erases backend gains

Mitigation:

- require persistent session reuse
- require batch flash support in the first implementation
- benchmark micro and short-run costs separately

## Risk: backend capability mismatch breaks helper logic

Mitigation:

- publish explicit capability flags
- keep narrow fallback paths for bubble-point, Cp, and phase enthalpy
- test degraded-capability backends intentionally

## Risk: refactor destabilizes parity behavior

Mitigation:

- preserve DWSIM as the first reference backend through Phases 1-4
- keep benchmark and regression runs active during each phase

## Risk: packet reuse becomes too aggressive

Mitigation:

- store provenance and validity windows on packets
- make thresholds configuration-driven
- keep trace markers showing fresh versus reused values

## Definition Of Done For This Branch

This branch is successful when all of the following are true:

- the runner builds thermo backends through one explicit factory
- the RHS uses a step-scoped thermo coordinator and shared packet
- duplicated flash and Cp work is materially lower on the benchmark cases
- a Clapeyron-targeted backend path exists behind the same contract
- at least one additional backend family (`thermo` or `ThermoPack`) can plug into the same architecture without another RHS rewrite
- a follow-up benchmark report demonstrates whether the win came from architecture, backend choice, or both

## Immediate Next Actions

1. Add the benchmark harness and saved baseline manifest.
2. Introduce the backend protocol and factory without changing runtime behavior.
3. Extract the thermo coordinator scaffold and migrate DWSIM through it first.
4. Collapse the duplicated tray refresh and vapor enthalpy refresh paths.
5. Only then bring up the Clapeyron-targeted backend path.
