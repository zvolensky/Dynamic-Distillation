# Core V3 Reporting Upgrade Requirements

Date: 2026-09-09
Status: Proposed
Owner: Dynamic Distillation Core V3

## 1. Purpose

Upgrade the Core V3 end-of-simulation report so that it supports three audiences:

- operators who need a fast answer about the run outcome;
- engineers who need evidence about process behavior, controls, balances, and limits; and
- reviewers who need reproducibility, provenance, and machine-readable evidence.

The upgraded report shall remain a presentation and interpretation layer. The
serialized simulation artifacts remain authoritative for scientific and numerical
results.

## 2. Scope

### In scope

- Core V3 DOCX and text-report content and structure;
- report-ready JSON and trajectory artifacts;
- verdict explanations and validity assessment;
- initial/final/delta operating metrics;
- constraint, balance, controller, event, and solver-health reporting;
- final thermal, hydraulic, and composition profiles;
- report provenance, artifact indexing, and schema versioning;
- focused automated tests for report content and data completeness.

### Out of scope

- changes to Core V3 equations, thermodynamic correlations, hydraulic equations,
  solver tolerances, controller laws, or acceptance gates;
- changing a simulation result because report generation fails;
- replacing CSV/JSON authority with DOCX;
- adding a new simulation or process-control feature solely to populate a report;
- claiming steady state from a report-only heuristic that is not part of the
  existing acceptance contract.

## 3. Existing Contract Constraints

The implementation shall preserve the rules documented in `docs/run_reports.md`:

1. Reports are generated after simulation and checkpoint serialization.
2. A report-generation failure is logged as `word_report_error` and does not
   invalidate or erase a completed simulation.
3. CSV/JSON artifacts remain the authoritative machine-readable record.
4. Geometry-based levels are reported as percentages only when geometry-based
   control is actually available.
5. Molar-holdup control shall be labeled in `lbmol`, not represented as a
   percentage level.
6. A `REVIEW` report is an audit aid and is not an accepted operating result.
7. Existing report consumers and the `--no-word-report` option remain compatible.

## 4. Report Design Principles

The report shall answer these questions in order:

1. Did the simulation complete?
2. Is the result acceptable, reviewable, or failed?
3. Why was that status assigned?
4. What process state was reached?
5. Were limits, balances, and controls satisfied?
6. What numerical evidence supports the result?
7. Where are the detailed artifacts?

The report shall use a layered structure:

- a concise decision summary;
- evidence tables and plots;
- detailed profiles and diagnostics;
- provenance and artifact references.

Raw precision shall be retained in machine-readable artifacts but reduced to
engineering-appropriate display precision in human-readable tables.

## 5. Status Vocabulary

The report shall use the following normalized statuses:

| Status | Meaning |
|---|---|
| `PASS` | Simulation completed and all required acceptance gates passed. |
| `REVIEW` | Simulation completed, but one or more warnings, incomplete evidence items, or non-acceptance conditions require review. |
| `FAIL` | Simulation did not complete, a hard stop occurred, or a required numerical/physical gate failed. |
| `NOT EVALUATED` | A requested assessment was not run or required data was unavailable. |
| `NOT APPLICABLE` | The assessment does not apply to this run configuration. |

The report shall distinguish:

- simulation completion status;
- numerical validity status;
- physical/process validity status;
- steady-state status; and
- overall report status.

The overall status shall not hide a failed subordinate status.

## 6. Required Report Sections

### RPT-001: Title and identity

The first page shall show:

- case name;
- run ID;
- Core V3 version or schema version;
- report schema version;
- run classification;
- start and end timestamps with timezone;
- simulated duration;
- wall-clock duration;
- simulation-to-wall-clock ratio;
- fresh-start or continuation status;
- source checkpoint, if any.

### RPT-002: Executive verdict

The first substantive section shall show:

- overall status;
- completion status;
- steady-state status;
- one-sentence interpretation;
- confidence/evidence completeness indicator;
- count of errors, warnings, and unevaluated checks;
- top three status reasons, ordered by severity.

Example:

```text
Overall status: REVIEW
Simulation completed: YES
Steady state: NO
Primary reason: Bottoms composition slope exceeded the steady-state criterion.
Evidence completeness: PARTIAL
```

### RPT-003: Ranked verdict reasons

Each reason shall contain:

- stable gate or check ID;
- severity;
- status;
- observed value;
- limit or target, when applicable;
- units;
- time of observation;
- location or variable;
- human-readable explanation;
- source artifact or data-quality note.

Reasons shall be deterministic for identical input artifacts.

### RPT-004: Initial, final, and delta summary

The report shall provide a table with at least:

- feed flow and component flows;
- distillate and bottoms flow;
- reflux flow;
- top and bottom pressure;
- top and bottom temperature;
- condenser and reboiler duty;
- terminal liquid and vapor inventory;
- terminal drum/sump level;
- product composition;
- controller PV, SP, and error;
- total liquid and vapor inventory.

Columns shall be:

```text
Variable | Initial | Final | Change | Minimum | Maximum | Units
```

When initial or extrema data is unavailable, the cell shall say `Not reported`
rather than silently using the endpoint value.

### RPT-005: Product results

For distillate and bottoms, report:

- phase;
- flow;
- temperature;
- pressure;
- molar enthalpy;
- molar density;
- component mole fractions;
- product targets, if configured;
- absolute and relative deviation from target, if configured.

Composition tables shall use one component per row rather than a long inline
composition string when more than two components are present.

### RPT-006: Operating-limit assessment

The report shall include a constraint table:

```text
Check | Variable | Limit/target | Observed | Time | Location | Status | Evidence
```

At minimum, assess when applicable:

- pressure lower and upper bounds;
- temperature lower and upper bounds;
- terminal level bounds;
- controller output bounds;
- positive inventories;
- valid mole fractions;
- valid phase/property calculations;
- flow limits;
- provider-call or timing hard stops;
- existing dynamic, physical, conservation, phase, geometry, and common-root gates.

Near-limit values shall be distinguishable from actual violations. The report
shall not infer a limit from plot range or formatting.

### RPT-007: Steady-state assessment

The report shall show:

- steady-state status;
- score;
- score limit;
- qualification window;
- minimum required simulation time;
- each score term;
- each raw metric;
- each tolerance;
- the controlling term;
- time interval used for the assessment.

The current criterion text, including the 60-second minimum and score limit,
shall be reported from the calculation contract rather than hard-coded only in
the DOCX formatter.

Display values shall include both readable engineering notation and the ratio to
limit. For example:

```text
Relative state rate: 2.1e-5 /s; limit 3.0e-3 /s; 0.007 of limit; PASS
```

### RPT-008: Material and energy balances

The report shall include a balance summary with:

- total material balance residual;
- component balance residual for every component;
- energy balance residual;
- maximum absolute residual;
- maximum normalized residual;
- integrated residual over the run;
- final-window residual;
- time of worst residual;
- volume/location of worst residual;
- balance tolerance and status.

Where full signed terms are available, provide:

```text
Time | Volume | Component/energy | In | Out | Accumulation | Residual | Normalized residual
```

Aggregate maxima shall not be presented as a complete balance ledger.

If only aggregate data is available, the report shall explicitly state:

```text
Balance detail: aggregate maximum only; signed per-volume ledger unavailable.
```

### RPT-009: Controller performance

For each active controller, report:

- controller name and controlled variable;
- PV, SP, and final error;
- maximum absolute error;
- mean absolute error;
- integral absolute error, when a complete history exists;
- overshoot and undershoot;
- settling time and settling criterion;
- output minimum and maximum;
- time at lower and upper saturation;
- output slew-rate maximum;
- tuning parameters;
- controller-data completeness.

Controller metrics shall not be calculated from endpoint-only data and labeled as
full-run performance.

### RPT-010: Event and disturbance timeline

The report shall include a chronological event table when event data exists:

```text
Time | Event type | Variable/component | Before | After | Consequence | Severity
```

Events shall include, when supported:

- initialization completion;
- feed or setpoint changes;
- thermo refreshes;
- property/flash failures and recoveries;
- solver retries or step reductions;
- active-bound transitions;
- controller saturation;
- checkpoint restore;
- steady-state qualification;
- hard stop and shutdown.

If no structured event stream exists, the report shall say:

```text
Event timeline: not available in this artifact version.
```

### RPT-011: Dynamic trends

Plots shall include, when data exists:

- feed, distillate, bottoms, and reflux flows;
- product composition and composition error;
- top/bottom pressure;
- top/bottom temperature;
- drum/sump PV and SP;
- controller output;
- condenser/reboiler duty;
- total liquid and vapor inventory;
- balance residuals;
- constraint margins.

Plots shall:

- use explicit units on axes;
- identify data source;
- mark disturbances and events;
- mark the steady-state qualification window;
- mark limit lines where limits exist;
- use separate axes when units differ materially;
- preserve legends and readable labels;
- avoid implying continuous data when the trajectory is sampled.

If a terminal value is used as a fallback for a missing history, the plot and
caption shall state that the series is a terminal-value fallback.

### RPT-012: Final profiles

Final profiles shall be separated into:

1. thermal and hydraulic profile;
2. liquid composition profile;
3. vapor composition profile.

The report shall include profile plots for:

- temperature versus stage/volume;
- pressure versus stage/volume;
- liquid and vapor internal traffic;
- liquid composition versus stage;
- vapor composition versus stage.

The profile summary shall identify:

- feed stage;
- condenser/reflux volume;
- reboiler/sump volume;
- top-to-bottom pressure drop;
- temperature range;
- composition extrema;
- missing or non-stage nodes;
- flow reversals or invalid values.

### RPT-013: Numerical-health summary

The report shall show, when available:

- integrator and nonlinear solver;
- configured tolerance;
- configured timestep and actual timestep statistics;
- accepted and rejected steps;
- nonlinear iterations;
- line-search and bound rejections;
- residual infinity norm;
- Jacobian rank and condition;
- objective, Jacobian, and provider-call counts;
- memoization/cache counts;
- initialization status;
- event-handling count;
- warning and error counts;
- solver/runtime timing breakdown;
- termination reason.

The report shall distinguish solver success from process acceptance. A numerically
successful run may still receive `REVIEW` or `FAIL` for physical, control, or
acceptance-gate reasons.

### RPT-014: Configuration and provenance

The report shall preserve:

- input workbook;
- exact launch command;
- model/provider identity;
- controller tuning;
- feed and disturbance configuration;
- timestep and requested duration;
- completed duration;
- checkpoint lineage;
- source file or package version;
- relevant contract/gate version;
- hashes or IDs for authoritative artifacts.

### RPT-015: Artifact index

The final section shall list available artifacts and status:

```text
Artifact | Path | Schema/version | Hash or size | Status
```

At minimum, include the endpoint JSON, trajectory/profile CSVs, checkpoint, text
summary, DOCX report, warnings/log, and report metadata.

## 7. Data and Persistence Requirements

### DAT-001: Report summary contract

Persist a versioned report summary with this logical structure:

```json
{
  "report_schema_version": "core-v3-report-v2",
  "run_id": "...",
  "overall_status": "PASS|REVIEW|FAIL",
  "completion": {},
  "steady_state": {},
  "verdict_reasons": [],
  "initial_final_delta": {},
  "constraints": [],
  "balances": {},
  "controllers": [],
  "numerical_health": {},
  "provenance": {},
  "artifacts": {}
}
```

### DAT-002: Report-ready trajectory

Persist a report-ready trajectory for accepted simulation steps. It shall include,
when applicable:

- time;
- feed and product flows;
- duties;
- pressure and temperature by volume;
- liquid/vapor inventories;
- liquid/vapor compositions;
- controller PV, SP, output, and error;
- constraint margins;
- balance residuals;
- event markers.

A documented downsampling strategy may be used, but all event points, extrema,
limit crossings, and steady-state qualification boundaries shall be retained.

### DAT-003: Balance ledger

Persist signed material and energy balance terms by time and volume whenever the
underlying calculations expose them. Aggregate maxima alone do not satisfy this
requirement.

### DAT-004: Event stream

Persist structured events as JSON records with:

- event ID;
- simulation time;
- event type;
- severity;
- variable/location;
- before and after values;
- message;
- source component;
- related gate or constraint.

### DAT-005: Controller history

Persist controller histories sufficient to calculate full-run performance metrics.
Endpoint-only controller data shall be marked as endpoint-only.

### DAT-006: Missing-data semantics

Every report data item shall have one of these states:

- `observed`;
- `derived`;
- `fallback`;
- `not_available`;
- `not_evaluated`;
- `not_applicable`.

The state shall be available to the formatter so missing evidence cannot appear as
an ordinary numeric result.

## 8. Compatibility Requirements

- Existing `core-v3-end-of-run-summary-v1` consumers shall continue to work.
- New fields shall be additive where practical.
- Existing field names and units shall not change without a schema migration.
- Existing reports shall remain readable when opened with the upgraded formatter.
- Reports generated from old artifacts shall identify their limited evidence level.
- `--no-word-report` shall continue to suppress DOCX creation.
- DOCX generation errors shall remain non-fatal.
- Text formatting shall remain deterministic for test fixtures.

## 9. Acceptance Criteria

### Functional

- A completed nominal run produces a report with an executive verdict, initial/final/delta table, limits table, steady-state breakdown, numerical-health summary, profile section, configuration, and artifact index.
- A not-steady run identifies the controlling steady-state term and reports the observed value and tolerance.
- A failed-gate run identifies each failed gate with observed value, limit, time, and location where available.
- A run with missing trajectory data states which sections are incomplete.
- A report never labels molar holdup as a percentage level.
- A fallback product-flow trend is explicitly labeled.
- A report-generation exception records `word_report_error` without changing the simulation result.

### Data integrity

- All reported numbers are traceable to an authoritative artifact or are labeled as derived.
- Derived values are reproducible from the persisted artifact.
- No endpoint value is silently substituted for a missing history.
- Report units match the underlying data units.
- Initial, final, minimum, and maximum values use the same declared data scope.

### Quality

- Tables repeat headers across DOCX page breaks.
- Long profile data is split into readable tables.
- Plots have units, legends, limit lines where applicable, and event/qualification markers.
- The report remains usable for both steady and transient endpoints.
- Report output is deterministic except for explicitly labeled generation timestamps.

### Testing

Add tests for:

- status and ranked verdict reasons;
- missing-data states;
- initial/final/delta calculations;
- constraint assessment;
- steady-state term formatting;
- material and energy balance summaries;
- controller KPI calculations;
- event ordering;
- profile table splitting;
- fallback trend labeling;
- old-schema compatibility;
- non-fatal report-generation failure;
- DOCX section presence and embedded chart count.

## 10. Implementation Phases

### Phase 1: Report-layer improvements

Use existing artifacts only:

- executive verdict;
- ranked existing gate reasons;
- initial/final/delta tables;
- improved steady-state explanation;
- numerical-health section;
- clearer units and precision;
- explicit missing/fallback labels;
- split profile tables;
- artifact index.

### Phase 2: Report-ready aggregation

Add a report summary builder that derives and persists:

- normalized constraints;
- profile extrema;
- aggregate balance summaries;
- controller endpoint and available-history metrics;
- evidence completeness state.

### Phase 3: Runtime instrumentation

Add persistence for:

- accepted-step report trajectories;
- structured events;
- signed material and energy ledgers;
- full controller histories;
- limit-crossing and saturation intervals.

### Phase 4: Comparative reporting

Add baseline/candidate inputs and report:

- KPI deltas;
- profile differences;
- constraint changes;
- balance changes;
- numerical-health changes;
- pass/fail comparison criteria.

## 11. Open Decisions

The implementation owner shall resolve these before Phase 2:

1. Whether the report-ready trajectory is CSV, Parquet, or JSON lines.
2. Whether all accepted steps or event/extrema-preserving downsampling is the default.
3. The authoritative source for gate definitions and tolerances.
4. Whether controller KPIs use the full run or only the post-disturbance window.
5. Whether balance tolerances are absolute, relative, or both.
6. Whether the DOCX is the only human-readable format or whether Markdown/HTML is
   also required.
7. How artifact paths and hashes are represented when files are moved or archived.

## 12. Definition of Done

The upgrade is complete when:

- the report schema is versioned;
- Phase 1 report improvements are implemented and tested;
- all unavailable evidence is explicitly labeled;
- the nominal, transient, failed-gate, continuation, and missing-artifact cases
  have report fixtures;
- the DOCX and text reports agree on status and key metrics;
- authoritative artifacts remain unchanged by report generation;
- documentation in `docs/run_reports.md` describes the new sections and data
  semantics;
- report-generation failures remain non-fatal and diagnosable.
