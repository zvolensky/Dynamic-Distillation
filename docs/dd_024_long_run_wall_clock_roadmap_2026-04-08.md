# DD-024 Long-Run Wall-Clock Roadmap

Date: April 8, 2026

## Purpose

This note reprioritizes the compute-efficiency refactor after the startup-seed work.

The new primary goal is:

- reduce total wall-clock time for meaningful dynamic runs
- drive the simulation-time to wall-clock-time ratio toward `1`

The startup path is no longer the main blocker.

## Current Position

## What was achieved

Recent work materially changed startup behavior on the depropanizer + Clapeyron path:

- prior fresh-startup behavior for this column had been on the order of `10-12 minutes` before the first logged row
- current fresh-process startup is now about `20-30 s`
- current loaded-seed first-step runtime is now about `0.18 s`

Representative references:

- fresh full-startup context:
  - `docs/cli.md`
  - `docs/excel_input_explainer.md`
- current loaded-seed fast path:
  - `logs/depropanizer_20stage_hydraulic_clapeyron_pr_startup_seed_probe_20260408e/run_metadata_20260408_114250.json`
  - `logs/depropanizer_20stage_hydraulic_clapeyron_pr_startup_seed_probe_20260408e/startup_trace_20260408_114224.log`

## What this means

Startup optimization is no longer the rescue mission.

It is now good enough for normal iteration. The main practical problem has shifted back to the bigger picture:

- long dynamic runs
- repeated thermo cost over many steps
- fresh-process backend bring-up when a new run starts

## Priority Decision

Startup-only cleanup is now lower priority.

The highest-value next work is anything that reduces:

1. per-step thermo burden across many timesteps
2. repeated cold backend setup across repeated runs
3. average thermo work per simulated second

## Main Roadmap

## Phase 1: Persistent Clapeyron Session Reuse

### Goal

Stop paying full Julia / Clapeyron cold-start cost on every new run.

### Why this is first

The current seeded runtime path is already cheap. The remaining fixed startup cost is mostly backend bring-up, not timestep orchestration.

If we can keep a warmed Clapeyron session alive across runs, we should improve:

- fresh restart wall time
- short benchmark turnaround
- controller-tuning workflow
- the viability of medium-length repeated experiments

### Recommended implementation shape

Introduce a persistent provider mode or sidecar mode that:

- owns one Julia session
- constructs the Clapeyron model once
- serves repeated thermo requests from Python runs in the same process or via a local service

Candidate options:

1. in-process persistent singleton owned by the runner process family
2. local long-lived worker process with a narrow request protocol
3. explicit service-mode launcher for benchmark and development workflows

### Success criterion

Reduce fresh-process startup from about `20-30 s` to single-digit seconds for repeated runs in a warm session.

## Phase 2: Frozen Thermo Cadence

### Goal

Reduce average thermo cost over long runs by not performing full live thermo on every step.

### Core idea

Decouple:

- integrator cadence
- thermo refresh cadence

The integrator can still step every `dt`, while full provider refresh happens every `N` steps or on demand.

Between refreshes:

- hold `HL`, `HV`, `K`, and/or `y*` fixed
- optionally use first-order corrections for enthalpy-sensitive paths

### Safety mechanism

Trigger an early thermo refresh when any tray exceeds a drift threshold such as:

- `|dT| > threshold`
- `|dP| > threshold`
- `|dx| > threshold`
- large energy-residual growth

### Why this matters

This is the strongest available lever for moving long-run wall time toward real-time behavior.

### Success criterion

Demonstrate a stable run where average wall time per simulated second improves materially when `thermo_every_n_steps > 1`, without unacceptable drift in key KPIs.

## Phase 3: Miss-Set Batch Optimization for Warm Runs

### Goal

Make warm thermo refresh cost scale with the number of trays that actually changed meaningfully.

### Core idea

Do not batch all trays blindly.

Instead:

- identify the trays that missed reuse
- batch only that miss set
- preserve same-step packet reuse for all others

### Why this matters

This complements frozen thermo cadence:

- cadence reduces how often full thermo runs
- miss-set batching reduces how expensive a thermo refresh is when it does run

### Success criterion

Show reduced backend-equivalent flash count and lower wall time on warm multi-step probes where only part of the column is moving.

## Phase 4: Medium and Long Benchmark Checkpoints

### Goal

Stop judging progress mainly by short startup probes.

### Required benchmark ladder

Use at least three levels:

1. short probe
   - quick correctness and hot-spot inspection
2. medium probe
   - enough steps to expose average warm-step cost
3. long probe
   - enough simulated time to matter for real use

Recommended depropanizer ladder:

1. `0.4 s` simulated
2. `30-60 s` simulated
3. `5-10 min` simulated

### Why this matters

The short probe helped us fix startup and first-step waste, but it is not sufficient for deciding whether we are actually approaching a sim/wall ratio near `1`.

### Success criterion

Maintain a benchmark table showing:

- startup wall
- runtime wall
- total wall
- simulated seconds
- effective sim/wall ratio

for each checkpoint.

## Phase 5: Backend Breadth Only After Throughput Proof

### Goal

Keep backend generality, but do not let it dilute the real-time objective.

### Direction

Support for `ThermoPack` and `thermo` remains desirable, but should follow proof that the new orchestration strategy actually improves long-run throughput.

That means:

- keep the backend contract flexible
- keep adapters easy to add
- do not spend the next major block of effort on adapter breadth alone

## What Is Now Lower Priority

The following are still valid improvements, but not top priority:

1. squeezing another few seconds out of fresh startup packet reuse
2. minor startup helper cleanup
3. startup-only packet carry-through beyond what is already done
4. broad backend adapter expansion before long-run throughput is proven

## Recommended Immediate Next Implementation

The best next implementation target is:

1. add a persistent Clapeyron session mode
2. benchmark repeated short and medium runs against it
3. then add frozen thermo cadence with safety refresh thresholds

This sequence is recommended because:

- persistent session reuse attacks the remaining fixed-cost startup tax
- frozen thermo cadence attacks the repeated cost that dominates long runs

Together, these two changes are the highest-probability path to materially improving the sim/wall ratio.

## Practical Target Framing

Near-term target:

- get multi-minute runs out of the multi-hour range

Better target:

- get `10 min` simulated into well under `1 hour` wall

Stretch target:

- approach near-real-time behavior on stable operating windows

The current branch is now in a much better place to pursue that larger goal because startup is no longer consuming most of the engineering attention.
