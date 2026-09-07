# Starting a New Column Simulation

Updated: 2026-09-02

## ChemSep results -> Excel input -> initialized state -> steady state -> dynamic run

This is the normal workflow for starting a new column case. It applies to any
component list and column topology. ChemSep supplies a useful steady-state
reference, but its output is not automatically a valid dynamic initial state.

The important distinction is:

- ChemSep gives us a reference solution and operating targets.
- Excel gives the simulator a normalized case definition.
- The initializer builds a state that is consistent with the simulator's own
  equations and property provider.
- A steady-state solve proves that the state does not have material or energy
  drift.
- A dynamic run starts only after that accepted state has been saved.

## What Core V3 supports today

The current Core V3 code contains most of the model pieces for this workflow,
but it is not yet one automatic command that accepts any ChemSep case and
produces a reusable Core V3 restart.

| Workflow stage | Current support | Current boundary |
|---|---|---|
| ChemSep results -> Excel | Partial | The loader accepts normalized `.xlsx` workbooks; it does not read ChemSep `.sep` files directly. The ChemSep-to-workbook mapping is still an operator step. |
| Excel validation and name mapping | Supported | Components, specifications, initial conditions, streams, geometry, and optional state/memory sheets are read and normalized. |
| Core V3 state construction and zero-time closure | Supported at equation level | Generic DAE contracts, live-property evaluation, bounds, rank checks, and zero-time audits exist. A general workbook-to-Core-V3 state adapter is still needed. |
| Core V3 steady-state solve | Supported at equation level | Generic stationary residuals and root kernels exist. The accepted runnable path is still wrapped around prepared case data and case-specific support. |
| Dynamic run from an accepted state | Demonstrated | The water-methanol path rebuilds an accepted root and advances it dynamically. A general Core V3 checkpoint/reload command is not yet complete. |
| End-of-run report | Supported | The generic report produces duties, product streams, levels, steady-state score, and tray profiles. |

In other words, the present code supports the mathematical stages, but the
complete general chain is still:

`arbitrary ChemSep case -> normalized Excel -> Core V3 state -> Core V3 steady root -> reusable Core V3 restart -> dynamic case`

The missing integration work is deliberately separate from the column
equations. It consists of a general case adapter, a workbook-driven Core V3
stationary-run command, and a native Core V3 state serialization/reload path.
Until those pieces are complete, the water-methanol runners are validation
drivers, not the general-purpose user interface.

## 1. Export and review the ChemSep result

Before opening the simulator, save the ChemSep result and record its provenance:

- case name, date, software version, and thermodynamic method;
- component names and their order;
- number of stages, feed stage, condenser type, and reboiler type;
- stage temperature, pressure, liquid and vapor flow;
- liquid and vapor composition on every stage;
- feed, distillate, bottoms, reflux, condenser duty, and reboiler duty;
- units for every quantity.

Check the ChemSep material and energy balances first. Also inspect the pressure
profile. A real column normally has a pressure loss from tray to tray; a
constant-pressure ChemSep profile is not a reason to force zero pressure drop
in the dynamic model. The Excel and runtime pressure profiles must be allowed
to follow the selected hydraulic and pressure-drop equations.

Confirm that the ChemSep boundary equipment matches the model topology. In
particular, decide whether the reboiler is partial or total and whether the
condenser and reflux drum are represented as separate inventories. Do not hide
this decision in a component-specific exception.

## 2. Prepare the Excel input

Start from the appropriate general-purpose template. Treat the workbook as a
case and layout file, not as a serialized dynamic checkpoint.

Populate or verify:

1. component names and molecular weights;
2. stage count, feed location, boundary equipment, and feed condition;
3. operating specifications and manipulated variables;
4. stage pressure and temperature seed values;
5. liquid/vapor flow and composition seed values;
6. condenser, reflux-drum, reboiler, and sump geometry;
7. level setpoints and controller tuning, if control is enabled;
8. units, signs, and stream naming.

The loader must normalize names, units, and ordering before creating a state
vector. It should reject missing, duplicated, or ambiguous component names.
Keep the original ChemSep export and the normalized workbook unchanged as
audit artifacts. Record the workbook hash in the run report.

## 3. Build and initialize the simulator state

Load the workbook and construct the model state by conserved control volume.
For each volume, initialize:

- liquid component inventory;
- vapor component inventory;
- total internal energy;
- temperature and pressure;
- phase totals and compositions;
- hydraulic and vapor-flow variables;
- terminal liquid inventories and vessel levels;
- controller memory, when a controller is active.

ChemSep values are initial guesses for these quantities. They are not fixed
truth. Recalculate thermodynamic properties with the runtime provider. Do not
blindly conserve a serialized ChemSep enthalpy if it does not match the
runtime's internal-energy basis.

Run the zero-time initialization audit before integrating. It should check, at
minimum:

- component reconstruction and phase totals;
- energy and volume closure;
- equilibrium or the selected phase-state relation;
- EOS pressure and vapor free volume;
- tray pressure-drop and vapor-flow closure;
- feed and terminal boundary ownership;
- positive inventories, pressures, temperatures, and flows;
- controller degree-of-freedom ownership;
- geometry-based terminal levels.

The initializer may use bounded solves, relaxation, or homotopy as numerical
tools. Those aids must not become accepted physics. A candidate that needs
clipping, an imported flow cap, a previous-step limiter, or an unreported
projection has not been initialized.

## 4. Drive the initialized state to steady state

Use the following order:

1. Evaluate and report the zero-time residuals.
2. Solve the algebraic closure required by the selected topology.
3. Solve the steady component and energy balances under the operating
   specifications.
4. Re-run all physical, hydraulic, thermodynamic, and terminal audits.
5. Check robustness from reasonable pressure and flow perturbations.
6. Run a short nominal dynamic smoke test.
7. Run a longer nominal hold if the smoke test passes.

Do not call a state steady merely because a solver returned success or because
the first dynamic step completed. The state must have small differential
material and energy rates, a closed whole-column balance, and no unowned
boundary state. Use the simulator's defined steady-state score and acceptance
threshold for the case; a passing numerical trajectory and a steady-state
qualification are separate results.

At the end of each qualification run, report:

- condenser and reboiler duty;
- distillate and bottoms stream flow, temperature, pressure, enthalpy, and
  composition;
- distillate-drum and bottoms-drum levels;
- steady-state score and its acceptance threshold;
- clock time/simulation time ratio;
- final tray temperature, pressure, inventory, flow, and composition profiles.

Save the complete report, machine-readable trajectory, and any accepted state
artifact. A native checkpoint is preferred because it preserves packed state,
thermodynamic memory, hydraulic memory, and controller memory. An Excel-only
restart remains provisional until a reload smoke test demonstrates equivalent
behavior.

## 5. Start a dynamic case from the accepted state

Begin every dynamic experiment from the accepted steady state or its verified
native checkpoint. Keep the case definition and the initial state separate.

For an open-loop case:

1. load the accepted state;
2. change the specified input, such as feed flow, feed condition, duty, or
   pressure specification;
3. leave the controllers disabled or in the explicitly selected open-loop
   mode;
4. run for the requested simulation time;
5. record the trajectory and final summary.

For a closed-loop case:

1. load the same accepted state;
2. activate the selected controllers with bumpless memory initialization;
3. verify that each controlled variable has one manipulated variable;
4. apply the disturbance or setpoint change;
5. monitor levels, product rates, pressure, temperature, composition, and
   conservation during the run;
6. remove temporary disturbances after the experiment and verify that the
   source case has returned to its nominal inputs.

A disturbance is experiment data, not a permanent case edit. The report should
state the disturbance magnitude and duration, whether it was active at the
end, and how restoration was verified.

## What counts as an accepted starting point?

Accept the state only when all applicable gates pass:

- the topology and boundary ownership are complete;
- local thermodynamic and volume closure passes;
- global pressure and vapor-flow closure passes;
- component and energy balances pass at steady state;
- the physical domain and vessel levels are valid;
- active controller ownership is structurally valid;
- the nominal dynamic smoke and any required reload test pass;
- the accepted artifact is identified and reproducible.

Use an explicit status such as `steady_initialization_accepted`,
`algebraically_consistent_not_steady`, or a specific closure-failure reason.
Do not infer acceptance from a scattered set of metrics.

## Practical lessons from the recent validation work

The recent water–methanol case illustrates the separation of these steps:

- a ChemSep-derived Excel profile was a useful seed, but it required a direct
  model-consistent stationary solve;
- a nonzero tray pressure profile was retained so the pressure-drop equations
  represented real hydraulic losses;
- geometry-based drum and sump levels were calculated from live density and
  vessel geometry;
- the 0.5-second dynamic handoff passed with both level controllers active;
- a sustained 5% feed increase produced a stable, conservative trajectory,
  but its 10-minute steady-state score was still above the steady criterion.

That last point is important: a dynamic run can be numerically successful and
physically well behaved while still being in transition. Continue the hold or
report it as a transient result rather than labeling it a new steady state.

## Related documents and artifacts

- [`initializer_how_to_guide.md`](initializer_how_to_guide.md) — detailed
  initializer design and diagnostic history;
- [`initializer_requirements_and_acceptance.md`](initializer_requirements_and_acceptance.md)
  — acceptance gates and required outputs;
- [`initialization_code_status.md`](initialization_code_status.md) — supported,
  experimental, and deprecated paths;
- [`dynamic_model_current_state_2026-08-20.md`](dynamic_model_current_state_2026-08-20.md)
  — current Core V3 model status;
- `logs/` and `docs/` — machine-readable trajectories and end-of-run reports.
