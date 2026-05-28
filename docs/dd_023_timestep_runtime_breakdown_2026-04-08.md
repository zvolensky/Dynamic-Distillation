# DD-023 Timestep Runtime Breakdown

Date: April 8, 2026

## Purpose

This note describes:

1. What the code does around each dynamic timestep in the current hydraulic + energy + Clapeyron path.
2. How much wall-clock time the current implementation spends on those timestep activities.

The goal is to separate:

- startup work, which happens before the first timestep
- per-timestep work inside the dynamic loop
- the specific thermo sub-steps that dominate wall time

## Source Runs Used

The primary reference is the current post-seeding short Clapeyron probe from April 8, 2026:

- `logs/depropanizer_20stage_hydraulic_clapeyron_pr_short_probe_20260405/run_metadata_20260408_090045.json`
- `logs/depropanizer_20stage_hydraulic_clapeyron_pr_short_probe_20260405/startup_trace_20260408_085952.log`

That run used:

- `thermo_mode = clapeyron`
- `runtime_mode = hydraulic`
- `n_steps = 2`
- `dt = 0.2 s`
- `elapsed_wall_sec = 0.43808980006724596` for `0.4 s` simulated runtime after logging started

For comparison, the pre-seeding cold-path reference from April 7, 2026 is:

- `logs/depropanizer_20stage_hydraulic_clapeyron_pr_short_probe_20260405/run_metadata_20260407_205910.json`
- `logs/depropanizer_20stage_hydraulic_clapeyron_pr_short_probe_20260405/startup_trace_20260407_205821.log`

Important caveat:

- The benchmark is very short, so it is excellent for locating hot spots, but it is not a perfect predictor of long-run average step cost.
- The progress line in the runner is cumulative wall time since runtime logging started, not a delta timer for one isolated RHS call. That behavior comes from `dynamic_run_scaffold_v1.py` where progress uses `time.perf_counter() - start_perf`.

Relevant code anchors:

- timestep loop and progress logging: `src/dynamic_distillation/dynamic_run_scaffold_v1.py:11192`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:11215`, `src/dynamic_distillation/dynamic_run_scaffold_v1.py:11267`
- explicit Euler step: `src/dynamic_distillation/dynamic_run_scaffold_v1.py:3046`
- main RHS function: `src/dynamic_distillation/column_rhs_v1.py:1136`

## Modules Involved

The current timestep path spans the following modules.

### 1. Runner / timestep loop

- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

Responsibilities:

- build the run inputs and thermo provider
- perform startup initialization before dynamic time advances
- drive the outer timestep loop
- call `column_rhs(...)`
- apply the integrator step
- emit progress lines, runtime trace lines, and snapshots

### 2. Main column RHS

- `src/dynamic_distillation/column_rhs_v1.py`

Responsibilities:

- unpack the state into tray holdup, pressure, energy, and temperature variables
- compute hydraulic and energy-model tray derivatives
- run the live thermo-dependent tray calculations
- resolve condenser and reboiler thermo duties
- build equilibrium split and interphase transfer targets
- return `dydt` plus diagnostics

This is the main owner of the expensive per-timestep work.

### 3. Thermo step coordinator

- `src/dynamic_distillation/thermo_step_coordinator_v1.py`

Responsibilities:

- coordinate tray thermo refresh work within one RHS call
- refresh current tray TP packets
- refresh energy-vapor-flow enthalpy packets
- refresh legacy temperature-state enthalpy packets
- manage same-step packet reuse and batch-vs-scalar flash selection

This module is the main orchestration seam for avoiding duplicate thermo flashes within a timestep.

### 4. Clapeyron thermo provider

- `src/dynamic_distillation/thermo_clapeyron_provider_v1.py`

Responsibilities:

- own the Python-facing Clapeyron backend adapter
- build and cache the Clapeyron model
- execute scalar and batch TP flashes
- provide enthalpy, Cp, liquid density, vapor Z, and bubble-point helpers
- maintain exact-state flash caches and liquid-density caches

This module owns the actual live property calls that dominate current wall time.

### 5. Thermo backend contract and factory

- `src/dynamic_distillation/thermo_backend_protocol_v1.py`
- `src/dynamic_distillation/thermo_backend_factory_v1.py`

Responsibilities:

- define the runtime-facing backend contract
- choose which thermo backend implementation is instantiated
- keep the runtime code decoupled from specific backends such as Clapeyron, DWSIM, table, or stub providers

These modules are less important to one timestep’s wall time, but they define how the timestep path obtains its thermo backend.

### 6. Benchmark harness and manifests

- `tools/bench_live_thermo_refactor_v1.py`
- `docs/thermo_refactor_benchmark_manifest_2026-04-05.json`

Responsibilities:

- run repeatable benchmark cases
- record wall time and run metadata
- provide the run artifacts used in this document

These are not part of timestep execution itself, but they are the measurement layer used to quantify it.

## What Happens Before the First Timestep

This is not timestep work, but it matters because it dominates wall time before simulation time starts advancing.

From `run_metadata_20260408_090045.json`:

- startup to logging-ready state took about `53.47 s`
- the biggest startup slice was vapor-holdup initialization:
  - `vapor_holdup_initialization = 23.8874 s`
  - `startup_tray_refresh = 23.8827 s`

So before the first dynamic step is even processed, the run has already consumed roughly `53.5 s` of wall clock.

## Timestep Loop Structure

At a high level, one dynamic cycle looks like this:

1. Evaluate `column_rhs(...)` for the current state.
2. Build diagnostics and thermo packets.
3. Advance the state with the selected integrator.
4. Log progress and snapshots.
5. Repeat.

In the current short benchmark, the integrator is explicit Euler, so the integration itself is cheap. Almost all meaningful wall time is inside `column_rhs(...)`.

## What `column_rhs(...)` Does Each Time

For the current hydraulic + energy + legacy temperature path, the main per-call sequence is:

1. Unpack the state vector and current tray variables.
2. Solve vapor-flow-by-energy closure and refresh provider enthalpies when live thermo is active.
   - key hook: `src/dynamic_distillation/column_rhs_v1.py:1976`
3. Resolve condenser duty and, when needed, perform a condenser thermo solve.
   - trace points emitted near `src/dynamic_distillation/column_rhs_v1.py:5190`
4. Build flash-consistent equilibrium split targets.
   - starts at `src/dynamic_distillation/column_rhs_v1.py:3773`
5. Build phase-holdup targets and interphase transfer terms.
6. Compute energy-holdup derivatives.
   - starts at `src/dynamic_distillation/column_rhs_v1.py:4000`
7. Run the legacy temperature-state block.
   - starts at `src/dynamic_distillation/column_rhs_v1.py:4132`
   - provider enthalpy refresh hook at `src/dynamic_distillation/column_rhs_v1.py:4197`
8. Return `dydt` and diagnostics.
   - return trace at `src/dynamic_distillation/column_rhs_v1.py:4621`

## Observed Timing in the Current Short Clapeyron Probe

### 1. First RHS Evaluation at Runtime Start

The first runtime RHS call is:

- `runtime_step_0:outer_rhs enter` at wall `53.47 s`
- `runtime_step_0:outer_rhs return` at wall `53.62 s`

Observed wall:

- first RHS call: about `0.15 s`

Inside that first RHS, the condenser no longer performs a fresh bubble-point helper solve. The trace shows immediate reuse of the startup-seeded packet:

- `condenser duty thermo solve reused previous packet T_vapor_in_F=126.824 P_cond_psia=220.440`

This means the first RHS call is now mostly the remaining tray-level thermo, equilibrium split, and temperature-state work.

Approximate breakdown of the first RHS call:

| Sub-step | Approx wall |
| --- | ---: |
| Energy vapor-flow enthalpy refresh | less than `0.05 s` at trace resolution |
| Condenser duty thermo solve | reused seeded packet |
| Equilibrium split + phase-holdup target build | about `0.03 s` |
| Legacy temperature-state refresh + tray loop | about `0.09 s` |
| Total first RHS call | about `0.15 s` |

The metadata supports the same conclusion:

- `condenser_duty_bubble_point_helper_flash` is absent from `thermo_call_counters`
- `energy_vapor_flow_enthalpy_refresh.wall_sec = 0.005758400075137615`
- `temperature_state_enthalpy_refresh.wall_sec = 0.007924700388684869`
- `temperature_state_cp_lookup.wall_sec = 0.006098700454458594`

### 2. Integration After the First RHS

Immediately after `runtime_step_0`, the runner performs explicit Euler integration:

- `step=0 integrate start`
- `step=0 integrate done wall=0.00s`

Observed wall:

- explicit Euler update: effectively `0.00 s` at trace resolution

So the integrator is not the current wall-time problem.

### 3. Follow-On RHS at `t = 0.2 s`

After the first integration, the runner evaluates the RHS again for the updated state:

- `runtime_step_1:outer_rhs enter` at wall `53.63 s`
- `runtime_step_1:outer_rhs return` at wall `53.73 s`

Observed wall:

- second RHS call: about `0.10 s`

What changed:

- the condenser path again reused the previous packet instead of doing a bubble-point helper solve
- many energy-vapor-flow and temperature-state enthalpy requests reused packets as well

The trace shows this explicitly:

- `condenser duty thermo solve reused previous packet`

So once the state is warm and packet-compatible, the RHS becomes much cheaper.

### 4. Progress-Line Interpretation

The first visible progress line is:

- `Progress step=1 sim_t=0.20 s wall=0.28 s`

That `0.28 s` is not just one isolated “step solve.” It spans:

- the first seeded RHS call
- the explicit Euler advance
- the next RHS/diagnostic evaluation for the updated state

That is why the trace shows both `runtime_step_0` and `runtime_step_1` before the first `Progress step=1` line.

### 5. Final Advance to `0.4 s`

The second visible progress line is:

- `Progress step=2 sim_t=0.40 s wall=0.31 s`

Incremental wall from the previous progress line:

- about `0.04 s`

That increment is tiny because this short probe stops immediately after the second explicit Euler advance. It does not include a full additional expensive RHS pass after `sim_t = 0.4 s`.

So `0.04 s` is not a reliable steady-state timestep cost by itself. It is just the final increment in a two-step benchmark that ends right after integration.

## Pre-Seeding Comparison

Before the condenser seed carry-through change, the equivalent cold-path reference run from April 7 looked very different:

| Runtime activity | April 7 cold path |
| --- | ---: |
| Startup before first runtime trace | `48.50 s` |
| First runtime RHS call | `9.25 s` |
| First explicit Euler update | `0.00 s` |
| Second runtime RHS call | `0.10 s` |
| Second explicit Euler update | `0.00 s` |
| Total runtime after logs opened | `9.46 s` |

That run spent about `9.13 s` in `condenser_duty_bubble_point_helper_flash` during the first runtime RHS, which is the cost the seeded packet now bypasses.

## Practical Interpretation

For the current short benchmark, the runtime behavior looks like this:

| Runtime activity | Approx wall |
| --- | ---: |
| Startup before first runtime trace | `53.47 s` |
| First runtime RHS call | `0.15 s` |
| First explicit Euler update | `0.00 s` |
| Second runtime RHS call | `0.10 s` |
| Second explicit Euler update | `0.00 s` |
| Total runtime after logs opened | `0.44 s` |

The key takeaway is:

- timestep wall time is not dominated by numerical integration
- it is dominated by thermo work inside `column_rhs(...)`
- the current seeded path removes the first-step condenser bubble-point penalty from runtime
- the remaining wall time is mostly startup tray refresh plus warm tray thermo work

## What This Means for “Per Timestep” Cost

There is not one single constant timestep cost in the current implementation.

Instead there are three regimes:

1. Startup regime
   - tens of seconds before the first timestep
2. Cold first RHS regime
   - about `9.25 s` in the old pre-seeding comparison run
3. Warm packet-reuse regime
   - about `0.10 s` for the immediate follow-on RHS in both the old and current runs
4. Seeded first-runtime regime
   - about `0.15 s` in the current run because the condenser packet is handed off from startup

That spread is why extrapolating long-run wall time from only one number is dangerous. Long runs will land somewhere between those extremes depending on:

- how often the condenser path can keep reusing the seeded or prior packet
- how often the condenser path has to fall back to a fresh bubble-point helper solve
- how often tray packets remain reusable
- whether thermo state drift invalidates same-step reuse

## Bottom Line

For the current Clapeyron path, each timestep effectively performs:

1. energy-vapor-flow thermo refresh
2. condenser-duty thermo resolution
3. equilibrium split construction
4. phase-holdup target construction
5. energy-holdup derivative evaluation
6. legacy temperature-state enthalpy and temperature update
7. state integration

In the best recent short run:

- the first runtime RHS consumed about `0.15 s`
- the condenser packet was reused from startup instead of paying a fresh bubble-point solve
- the immediate follow-on RHS consumed only about `0.10 s`
- explicit Euler integration itself was negligible

So the present wall-clock problem is still primarily a thermo-evaluation problem, not an ODE integrator problem, but the bottleneck has shifted. The dominant runtime penalty identified in the earlier cold-path audit has been removed from the first timestep, and the next major target is the `~53.5 s` startup burden before dynamic time begins.
