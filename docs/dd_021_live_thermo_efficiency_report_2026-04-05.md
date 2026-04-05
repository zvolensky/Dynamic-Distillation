# Live-Thermo Efficiency Report

Date: 2026-04-05

Scope: recent work over the last several days to improve non-tabular thermo runtime efficiency, with emphasis on live DWSIM hydraulic and parity runs for the water-methanol 10-stage case and the depropanizer hydrocarbon case.

## Executive Summary

The core problem is no longer correctness or workbook structure. The current blocker is runtime cost in the live thermo path. The model makes too many expensive thermo calls per simulated second, and many of those calls are still full tray-by-tray flash or flash-like property evaluations.

The recent effort did produce real gains:

- The best comparable water-methanol hydraulic 2-step probe improved from `538.57 s` wall to `133.31 s` wall.
- That is a reduction of about `405.26 s`, or `75.2%`.
- The first logged runtime step improved from about `350.00 s` wall to `79.67 s`, or about `77.2%`.
- Depropanizer live-DWSIM hydraulic startup to opened logs improved from about `7545.02 s` to `178.53 s`, or about `97.6%`.

Those are meaningful improvements. But they do not yet make live DWSIM hydraulic runs practical for multi-minute simulation horizons:

- Water-methanol hydraulic probe extrapolates to about `23-24 h` for `300 s` simulated time.
- Depropanizer hydraulic probe extrapolates to about `68 h` for `300 s` simulated time.

## Essence Of The Problem

The live thermo path is expensive because the runtime still pays for multiple overlapping thermo jobs:

- main tray flash refreshes
- vapor-flow enthalpy refreshes
- temperature-state enthalpy/Cp work
- condenser/reboiler helper flashes
- startup-only thermo conditioning and related initialization passes

Several of those jobs use the same or nearly the same tray states, but historically they were still making separate provider calls. The result is that the model can perform hundreds of direct flash requests, and over a thousand backend-equivalent flash operations, per simulated second in short hydraulic runs.

The problem is architectural more than package-specific. The April 2 live-DWSIM microbenchmark on the seeded water-methanol tray states showed no decisive package win inside DWSIM itself:

- `UNIFAC`: about `10.56 s` per 8-tray internal flash sweep
- `NRTL`: about `10.38 s`
- `UNIQUAC`: about `10.45 s`
- `Raoult`: about `10.46 s`
- `SRK`: about `11.12 s`
- `PR`: about `15.52 s`

So switching DWSIM property packages alone is unlikely to create a runtime breakthrough.

## Main Causes Identified

The recent diagnostics point to five main causes:

1. Repeated live tray-flash sweeps during startup and marching.
2. Separate enthalpy and Cp refresh paths revisiting states that were already flashed earlier in the same step.
3. Cp lookups that translate into multiple backend flash-equivalent operations.
4. Expensive helper flashes for condenser-duty and related top-end support logic.
5. A scalar live-DWSIM path in this repo, rather than a batch or parallel flash path.

For non-ideal systems like water-methanol, the activity-coefficient flash work makes the call-count problem hurt even more. But the hydrocarbon depropanizer evidence shows the architectural issue is not limited to non-ideal systems.

## Diagnostic Work Added

The following diagnostics were added during this effort and were critical to finding the real hotspots:

- line-buffered startup trace logging
- backend trace markers around live flash calls
- step-level runtime trace markers around `column_rhs`
- thermo call counters by category
- wall-time accounting by thermo category
- stage-level trace markers for main flash and enthalpy-refresh sections

These diagnostics changed the work from guesswork to measurement. The main remaining hot buckets are now visible instead of inferred.

## Main Code Modules Involved

The efficiency work described here touched a fairly concentrated part of the codebase. The main modules involved are:

- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
  - runner startup policy
  - thermo cadence decisions
  - startup trace logging
  - runtime trace markers
  - carryover of thermo packets and startup state into runtime
  - metadata snapshotting of thermo counters and timed buckets

- `src/dynamic_distillation/column_rhs_v1.py`
  - the main runtime RHS thermo work
  - `main_tray_refresh`
  - `energy_vapor_flow_enthalpy_refresh`
  - `temperature_state` enthalpy and Cp logic
  - condenser-duty helper logic
  - thermo-packet creation, reuse, and fallback behavior

- `src/dynamic_distillation/thermo_provider_v1.py`
  - provider-facing thermo call accounting
  - Cp caching
  - category tagging for thermo requests
  - preservation of timed counters and backend-equivalent flash counts

- `src/dynamic_distillation/pr_flash_backend_v1.py`
  - backend flash tracing
  - low-level flash and property timing visibility
  - bubble-point helper behavior and related backend instrumentation

- `tests/test_dynamic_run_scaffold_v1.py`
  - regression coverage for startup flags, runtime carryover, and counter snapshotting

- `tests/test_column_rhs_v1.py`
  - regression coverage for thermo-packet reuse, enthalpy/Cp fallback logic, and helper-path behavior

- `tests/test_thermo_provider_v1.py`
  - regression coverage for thermo accounting and provider-level caching/trace behavior

The work was therefore not spread uniformly across the whole simulator. It was concentrated mainly in the runner, the core RHS thermo path, the thermo provider wrapper, and the backend flash shim.

## Benchmark Baselines And Current State

### Water-Methanol Parity Baseline

Completed live-DWSIM parity benchmark from April 2:

- Run: `20260402_140016`
- Case: water-methanol, `dwsim + unifac`, parity, `thermo_every=5`
- `60 s` simulated time completed in `1920.81 s` wall
- About `32.0 min` total
- About `31.6 wall-s / sim-s` from `1 -> 60 s`

This proved parity could run end-to-end, but it remained far too slow for hydraulic ambitions.

### Water-Methanol Hydraulic Progression

Comparable 2-step hydraulic probe progression:

| Run ID | Main idea | Wall time for `0.4 s` sim | Improvement vs `20260403_123702` |
|---|---|---:|---:|
| `20260403_123702` | `bubblefast` baseline | `538.57 s` | baseline |
| `20260403_184050` | condenser-duty reuse across steps and within RHS | `255.20 s` | `52.6%` |
| `20260403_190925` | conservative temperature-state Cp reuse | `186.05 s` | `65.5%` |
| `20260404_124548` | `fast_startup` / eq-relax PR provider fix | `181.81 s` | `66.2%` |
| `20260404_150353` | startup thermo-packet carryover into runtime, tighter step-0 gate | `157.50 s` | `70.8%` |
| `20260404_162348` | reuse vapor enthalpy already computed by `energy_vapor_flow` | `133.31 s` | `75.2%` |

Best current short hydraulic benchmark:

- Run: `20260404_162348`
- Case: water-methanol, `dwsim + unifac`, hydraulic
- `0.4 s` simulated in `133.31 s` wall
- step 1 at `79.67 s` wall

### Depropanizer Hydraulic Comparison

Historical bad live-DWSIM hydraulic depropanizer reference:

- Run: `20260331_234952`
- Opened logs at `7545.02 s`
- First visible progress line was still only `step=0`, `sim_t=-0.00 s`, after another `544.40 s`

Current capped hydraulic depropanizer probe:

- Run: `20260404_180117`
- Opened logs at `178.53 s`
- `runtime_step_0:outer_rhs return` at `333.87 s`
- `runtime_step_1:outer_rhs return` at `504.91 s`

So startup pain on the depropanizer is dramatically better than it was, but the live hydraulic path is still not remotely practical for multi-minute runs.

## Targets And Outcomes

The following targets were investigated during this effort.

### Targets That Produced Clear Improvements

| Target | What changed | Outcome |
|---|---|---|
| Startup diagnostics and backend trace | Added flush-safe startup trace and backend flash markers | Essential for locating hangs and measuring thermo buckets |
| Flash accounting | Added thermo counters and timed buckets by category | Essential for proving where time was actually going |
| Parity startup cleanup | Skipped parity-only startup work that did not materially help smoke runs | Enabled parity runs to progress and write real outputs |
| `fast_startup` behavior fix | Made `--fast-startup` actually skip the documented heavy startup passes | Reduced startup waste and restored intended fast path |
| Selective eq-relax PR provider build | Avoided pointless duplicate live-provider use when main thermo was already DWSIM | Removed duplicate thermo sweep behavior |
| Thermo packet plumbing | Introduced and carried a reusable tray thermo packet across steps | Enabled later reuse optimizations |
| Vapor-side reuse tolerance split | Separated vapor reuse gate from liquid reuse gate | Improved vapor-side reuse safely |
| Bubble-point fast path | Added local-bracket fast path in bubble-point helper | Cut helper wall time materially in hydraulic probes |
| Condenser-duty reuse across steps | Reused total-condenser duty results when inlet vapor state had not changed much | Halved condenser-duty helper flashes in the hydraulic probe |
| Condenser-duty reuse within same RHS | Reused the same duty solve across later blocks in the same RHS | Further reduced redundant top-end helper work |
| Lighter default `energy_vapor_flow` Cp policy | Avoided live provider Cp in that path by default | Eliminated the `energy_vapor_flow_cp_lookup` bucket cleanly |
| Conservative temperature-state Cp reuse | Used packet/enthalpy slope where stable | Improved short hydraulic benchmark further |
| Startup packet carryover into runtime | Seeded runtime with startup thermo packet and used a tight step-0 refresh gate | Reduced `main_tray_refresh` and `energy_vapor_flow_enthalpy_refresh` at runtime step 0 |
| Same-step vapor enthalpy reuse | Reused vapor enthalpy already computed by `energy_vapor_flow` in `temperature_state` | Dropped `temperature_state_enthalpy_refresh` from `34` flashes to `4` in the best run |

### Targets That Did Not Improve Wall Time

These were tested and backed out because they either made wall time worse or did not help enough:

- looser general vapor packet reuse thresholds
- aggressive same-step packet reuse in `temperature_state`
- direct phase-enthalpy property calls as a substitute for the enthalpy-refresh path
- startup-only condenser-duty suppression / top-drum steadying skip
- startup `Z`-only initializer stripping
- split-only `main_tray_refresh`
- broad Cp carry-forward in the thermo packet
- naive condenser-duty helper cache experiments
- helper-only Cp threshold tweaks
- enthalpy estimate from previous packet in `energy_vapor_flow`
- conservative main-tray micro-reuse gate

This is an important result by itself: lowering flash counts is not sufficient if the change leaves expensive work on the critical path or shifts cost into slower replacement calls.

## Current Diagnostic Findings

The current best short hydraulic run is `20260404_162348`. In that run:

- `main_tray_refresh`: `60` flash requests, about `71.14 s`
- `energy_vapor_flow_enthalpy_refresh`: `60` flash requests, about `70.99 s`
- `temperature_state_enthalpy_refresh`: `4` flash requests, about `4.69 s`
- `condenser_duty_bubble_point_helper_flash`: `6` flash requests, about `7.29 s`
- `condenser_duty_helper_flash`: `6` flash requests, about `7.36 s`
- `reboiler_equilibrium_helper_flash`: `8` flash requests, about `9.70 s`
- `temperature_state_cp_lookup`: `248` backend flash equivalents
- `bottom_sump_cp_lookup`: `24` backend flash equivalents

The dominant remaining runtime costs are therefore:

1. `main_tray_refresh`
2. `energy_vapor_flow_enthalpy_refresh`
3. `temperature_state_cp_lookup` as backend flash-equivalent work

The earlier condenser-duty loop, which was once a major offender, is no longer the dominant problem after the reuse work.

## How Many Flashes Are Performed Per Simulated Second?

Using the current best water-methanol hydraulic short benchmark (`20260404_162348`):

- simulated time completed: `0.4 s`
- direct flash requests recorded: `144`
- backend flash-equivalent count recorded: `416`

That corresponds to roughly:

- direct flash requests: `360 flashes / simulated second`
- backend flash equivalents: `1040 flash-equivalents / simulated second`

Breakdown per simulated second from that run:

| Category | Count over `0.4 s` | Per simulated second |
|---|---:|---:|
| `main_tray_refresh` | `60` | `150/s` |
| `energy_vapor_flow_enthalpy_refresh` | `60` | `150/s` |
| `temperature_state_enthalpy_refresh` | `4` | `10/s` |
| `reboiler_equilibrium_helper_flash` | `8` | `20/s` |
| `condenser_duty_bubble_point_helper_flash` | `6` | `15/s` |
| `condenser_duty_helper_flash` | `6` | `15/s` |
| `temperature_state_cp_lookup` | `248` backend equivalents | `620/s` |
| `bottom_sump_cp_lookup` | `24` backend equivalents | `60/s` |

The Cp-related backend-equivalent counts are especially important because they show why a simple “flash request count” can understate the real thermo burden.

## What A Longer Run Still Looks Like

Even after the recent improvements, live hydraulic DWSIM remains too slow for practical multi-minute simulation:

### Water-Methanol

Current capped 5-minute-simulation hydraulic probe:

- Run: `20260404_181450`
- Reached `sim_t = 2.8 s` by `819.37 s` wall
- Sustained early marching rate: about `275-286 wall-s / sim-s`
- Extrapolated `300 s` hydraulic run: about `23-24 h`

### Depropanizer

Current capped 5-minute-simulation hydraulic probe:

- Run: `20260404_180117`
- Opened logs at `178.53 s`
- Reached `runtime_step_1:outer_rhs return` by `504.91 s`
- Early extrapolation: about `816 wall-s / sim-s`
- Extrapolated `300 s` hydraulic run: about `68 h`

So the present state is:

- much better than the earlier March live-DWSIM behavior
- still not practical for day-to-day multi-minute hydraulic iteration

## What Could Make DWSIM Practical Next?

The tactical wins appear to be nearing diminishing returns. The next gains likely require larger structural changes rather than more micro-threshold tuning.

Most promising next steps:

1. Collapse shared thermo work between `main_tray_refresh` and `energy_vapor_flow_enthalpy_refresh`.
   The two biggest remaining buckets are both live enthalpy/flash paths. A stronger shared per-step thermo/enthalpy packet should reduce duplicate work more effectively than the smaller helper-level tweaks.

2. Refactor Cp handling in the remaining temperature-state path.
   The current best run still shows `620` backend flash-equivalents per simulated second just from `temperature_state_cp_lookup`.

3. Reduce live refresh frequency selectively rather than globally.
   Commercial tools usually win by doing fewer full thermo solves, not just faster ones. A more deliberate refresh policy based on state movement may help more than further local caches.

4. Add a richer batch or parallel path for live thermo.
   The repo’s live DWSIM path is still scalar. If DWSIM itself cannot be used safely in batch/threaded form, another backend may ultimately be needed for a real breakthrough.

5. Explore a more efficient non-DWSIM live backend.
   Recent evidence suggests that simply changing DWSIM property packages is not enough. A different live engine with stronger batch behavior or lower per-call overhead may be required.

6. Revisit surrogate thermo, but only if it can be made trustworthy.
   The PR-backed table path is not currently trusted for the difficult cases, but a redesigned, validated surrogate may still be necessary if live hydraulic runs are to become practical.

## Non-DWSIM Live Backend Candidates

Recent review of open-source candidates suggests that there are plausible non-DWSIM live-backend options, but each comes with a different tradeoff between integration cost and performance upside.

### `Clapeyron.jl`

Why it is interesting:

- broad thermodynamic model framework
- activity-model support including `NRTL`, `UNIQUAC`, and `UNIFAC`
- likely the strongest raw-performance upside among the open-source candidates considered

Why it is harder:

- would require a Julia bridge from this Python codebase
- operational complexity is higher than a pure-Python drop-in
- benchmarking would be needed to confirm whether the backend advantage survives the bridge overhead

Current assessment:

- best long-term non-DWSIM live-backend candidate if performance is the priority

### `ThermoPack`

Why it is interesting:

- compiled thermodynamic library designed for heavy numerical calculations
- Python wrapper already exists
- better odds of real per-call speedup than a pure-Python backend

Why it is harder:

- integration will still be nontrivial
- exact fit for the water-alcohol gamma-phi workflow needs validation
- likely easier to adopt than a Julia stack, but less obviously broad than Clapeyron for this specific investigation

Current assessment:

- strongest compiled-Python candidate
- probably second-best performance bet after `Clapeyron.jl`

### `thermo`

Why it is interesting:

- Python-native, open source, and comparatively easy to integrate into the current repo
- supports chemical constants, mixture properties, flashes, and activity-coefficient workflows
- would likely be much easier than DWSIM to instrument, cache, and reshape around the runtime architecture

Why it is limited:

- less likely to deliver a dramatic raw-performance breakthrough by itself
- if the current architecture still asks for too many live flashes, a Python-native backend may still be too slow

Current assessment:

- best near-term prototype backend
- best choice if maintainability and experimentation speed matter more than maximum raw speed

### Lower-Priority Candidate

`PhasePy` remains a lower-priority option. It is open source and useful for VLE/modeling work, but it appears less turnkey on component/model parameterization and was not judged as strong a fit for this repo as the three candidates above.

### Recommended Ranking

If the goal is the best chance of making live non-tabular runs practical, the candidate ranking at this stage is:

1. `Clapeyron.jl` for the highest performance upside
2. `ThermoPack` for the strongest compiled backend with Python access
3. `thermo` for the easiest credible prototype path

The main caution is the same one revealed by the DWSIM work: backend speed alone probably will not solve the problem if the runtime architecture continues to request too many live thermo evaluations. A backend change and a structural reduction in thermo call count are likely complementary, not interchangeable, solutions.

## Conclusion

The recent work materially improved live-thermo efficiency. Startup waste is much lower, condenser-duty helper churn is no longer dominant, and the water-methanol hydraulic short benchmark improved by about `75%`. The depropanizer live-DWSIM startup path also improved dramatically.

But the system is still performing too many live thermo evaluations per simulated second. At the current best checkpoint, the water-methanol hydraulic short run still implies about `360` direct flash requests per simulated second and about `1040` backend flash-equivalents per simulated second. That is why live hydraulic DWSIM remains impractical for `300 s` runs even after substantial optimization.

The next meaningful runtime breakthrough is unlikely to come from another small cache tweak. It will likely require either:

- a stronger shared thermo/enthalpy refactor,
- a more aggressive reduction in live thermo call count,
- a trustworthy faster surrogate,
- or a more efficient non-DWSIM live backend.
