# Simulation UI Workflow Roadmap

Updated: 2026-09-02

## Product direction

The UI should use a limited, batch-oriented workflow as its primary operating
model. Users define a case, initialize and qualify it, run a controlled
simulation, and inspect the resulting reports. The interface should provide
rich observability without becoming a second simulation engine.

The UI may later support explicitly modeled runtime events, such as a feed
step, setpoint change, disturbance, or controlled shutdown. Arbitrary editing
of flows, temperatures, or controller values during a run is out of scope for
the initial workflow. Every runtime event must be recorded so a case remains
reproducible.

The technical ChemSep-to-Excel-to-dynamic sequence is documented in
[`new_simulation_workflow_chemsep_to_dynamic.md`](new_simulation_workflow_chemsep_to_dynamic.md).
This document describes how that sequence should be exposed to users.

## Navigation

The planned top-level sections are:

1. **New Simulation** — create a case from a workbook and qualify its initial state.
2. **Run Setup** — choose an accepted case, configure the experiment, and review the launch summary.
3. **Run Monitor** — follow progress, solver status, health metrics, and safe stop controls.
4. **Results** — inspect plots, profiles, tables, balances, and acceptance reports.
5. **Cases and Checkpoints** — browse reusable cases, provenance, artifacts, and prior runs.

## New Simulation

New Simulation is a first-class page, separate from ordinary run setup. Its
purpose is to turn a workbook seed into a traceable simulation case.

### 1. Choose source

- Upload or select a normalized `.xlsx` workbook.
- Identify the case name and preserve the original workbook as an immutable
  audit artifact.
- Explain that ChemSep `.sep` files require operator conversion to the
  normalized Excel format before ingestion.
- Optionally select an existing case as a comparison baseline.

### 2. Review workbook

Show the detected column definition before initialization:

- components and ordering;
- number of stages and feed stage;
- condenser, reflux drum, reboiler, and sump topology;
- temperatures, pressures, flows, compositions, and inventories;
- operating specifications and controller declarations;
- units, signs, and missing or ambiguous values.

The page should provide a compact preview and validation errors, rather than
requiring users to inspect the workbook manually.

### 3. Map and validate topology

Require confirmation or successful inference of:

- stage indexing and feed location;
- component-name mapping;
- condenser and reflux-drum ownership;
- reboiler and sump ownership;
- feed, product, reflux, and duty streams;
- active controller/manipulated-variable ownership.

Missing, duplicated, or ambiguous mappings must block initialization.

### 4. Build the initial state

Construct the state by conserved control volume and report:

- total component inventories;
- total internal energy;
- phase amounts and compositions;
- pressure and temperature profiles;
- hydraulic and vapor-flow variables;
- terminal inventories and levels;
- controller memory when applicable.

Imported workbook values are seed data and initial guesses. They must not be
presented as an accepted dynamic state merely because the workbook loaded.

### 5. Qualify the initializer

Run the documented gates in order:

1. local thermodynamic, energy, and volume closure;
2. global pressure and vapor-flow closure;
3. terminal-equipment closure;
4. controller degree-of-freedom audit;
5. zero-time residual evaluation;
6. optional bounded residual or stationary solve;
7. dynamic smoke test;
8. optional native checkpoint reload test.

A failed algebraic gate must prevent the dynamic smoke test from being used as
evidence of acceptance. Relaxation, homotopy, clipping, imported flow caps,
and previous-step limiters may aid diagnosis but cannot silently define an
accepted state.

### 6. Present an explicit verdict

The result must use a stable classification, for example:

- `local_uv_failed`;
- `local_uv_passed_global_hydraulics_failed`;
- `terminal_mapping_failed`;
- `algebraically_consistent_not_steady`;
- `steady_initialization_accepted`.

Display the failed gate, dominant residual blocks, worst stages/components,
comparison to the baseline seed, and the reason the candidate is or is not
usable. Do not make users infer acceptance from separate metrics.

### 7. Save the case and artifacts

A saved case should retain:

- normalized case definition;
- original workbook and workbook hash;
- initialization parameters and runtime configuration;
- residual and dynamic-gate reports;
- initializer execution log;
- native checkpoint, when accepted;
- provisional or diagnostic workbook exports, clearly labeled;
- restart metadata and command.

Native checkpoints are preferred because they preserve packed state and
runtime memory. An Excel-only restart remains provisional until reload parity
has been demonstrated.

## Run Setup

Run Setup consumes a saved case. It should not repeat workbook mapping or
initialization. The user selects:

- accepted case or explicitly permitted provisional case;
- open-loop or closed-loop mode;
- simulation duration and validated timestep;
- controller setpoints and tuning exposed by the case;
- feed, duty, pressure, or other declared experiment inputs;
- optional predefined disturbances and their duration;
- run name and description.

Before launch, show the source case, initial-state artifact, acceptance
classification, inherited controller state, and all runtime overrides.

## Run Monitor

The monitor should emphasize health and progress rather than editing model
state. It should show:

- simulated time, wall time, and estimated remaining time;
- run status and solver activity;
- steady-state score and relevant acceptance thresholds;
- material and energy balance drift;
- pressure, temperature, level, and composition trends;
- controller saturation, instability, or constraint warnings;
- hydraulic envelope status when available;
- pause, extend, cancel, and safe-stop actions.

Later runtime interventions must be predefined, validated, timestamped, and
included in the run metadata.

## Results

Results should provide:

- interactive time-series plots;
- stage temperature, pressure, flow, and composition profiles;
- product streams and condenser/reboiler duties;
- vessel levels and controller performance;
- material and energy balance tables;
- initializer and dynamic acceptance reports;
- warnings and failure reasons;
- exportable tabular data and report artifacts;
- comparison against the baseline or another saved run.

Results are a separate workspace from live monitoring so a completed run can
be reviewed without relying on the active-run state.

## Implementation milestones

- [ ] Define the simulation case data model.
- [ ] Design the New Simulation workflow and page states.
- [ ] Implement workbook ingestion, preview, and topology mapping.
- [ ] Implement initialization qualification and explicit verdicts.
- [ ] Persist cases, artifacts, checkpoints, and execution logs.
- [ ] Connect accepted cases to Run Setup.
- [ ] Build the run monitor and health views.
- [ ] Build the results and comparison workspace.
- [ ] Add focused workflow tests and operator documentation.

## Current implementation boundary

The existing Streamlit UI supports workbook selection/upload, checkpoint
restart, run launch, polling-based progress, trends, stage profiles, and
results for the available runners. Core V3 fresh initialization from Excel is
not yet exposed as a complete general-purpose workflow. The first UI delivery
should therefore implement the New Simulation page around the existing
validation and initializer tools while keeping diagnostic, provisional, and
accepted artifacts visibly distinct.
