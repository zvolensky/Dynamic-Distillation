# Human-Readable Run Reports

Completed logged simulations generate a Microsoft Word report beside the raw
CSV and checkpoint artifacts. The report is intended for operator inspection,
engineering review, and archival use; the CSV files remain the authoritative
machine-readable record.

## Contents

Each report includes:

- local start and completion time, case name, run ID, and description;
- input workbook and native-checkpoint lineage;
- fresh-start versus continuation status;
- elapsed wall time, simulated time, and simulation/wall-clock ratio;
- key simulation and controller parameters plus the exact launch command;
- starting and ending feed, product, pressure, temperature, duty, inventory,
  controller, and product-composition conditions;
- time-series charts for feed and products, internal traffic, pressure,
  vessel levels, duties, and level-controller outputs;
- final temperature, pressure, liquid-flow, vapor-flow, and composition tray
  profiles; and
- an automated validity note when the dynamic gate fails, thermo flashes fail,
  or a requested geometry-level loop falls back to molar holdup.

The output filename is `run_report_<run_id>.docx` in the run's log directory.

## Runtime Behavior

Word-report generation is enabled by default for completed runs that write log
files. Report generation occurs after simulation and checkpoint serialization.
An error in the reporting layer is logged as a warning and does not invalidate
or erase a completed simulation.

Use `--no-word-report` to suppress report generation for a particular run.

Core V3 dynamic runs also generate a DOCX report after their JSON and trajectory
artifacts are written. The Core V3 report uses the structured end-of-run summary
and saved trajectory evidence to include operating results, final inventories
and flows, provenance, configuration, and multi-panel dynamic trend charts.
Report-generation failures are recorded in run metadata as
`word_report_error` without changing the simulation result.

## Core V3 reporting schema v2

The reporting upgrade is delivered in manageable blocks:

1. **Report layer (implemented):** executive verdict, deterministic ranked
   reasons, initial/final/delta table, steady-state terms, limit assessment,
   numerical-health and provenance sections, split profile tables, and artifact
   index.
2. **Report-ready aggregation (implemented for evidence already saved):** the
   DOCX companion and the main `run_core_v3_dynamic.py` path write a
   `*.report_summary.json` sidecar using `core-v3-report-v2`. The runner uses a
   documented adapter over its existing summary CSV; it is additive to the
   existing `core-v3-end-of-run-summary-v1` payload and never changes it.
3. **Runtime instrumentation (implemented where exposed):** the main Core V3
   runner persists every accepted endpoint in `report_trajectory_*.jsonl`, a
   chronological `report_events_*.jsonl`, and signed global-component balance
   terms in `report_balance_ledger_*.jsonl`. These are additive evidence
   artifacts; the existing CSV/JSON/checkpoint records remain authoritative.
   The main Core V3 endpoint contract exposes signed global-component and
   per-volume energy terms; it does not expose per-volume signed component
   terms, which remain explicitly unavailable.
   No downsampling is applied to the accepted-step trajectory.
   If the nonlinear solve raises or an endpoint fails its acceptance gates, the
   event stream is flushed immediately with a `hard_stop` record before the
   runner propagates the failure.
   The water-methanol dual-level control runner now emits the same three
   report-evidence artifacts for each completed run: accepted controller
   PV/SP/output history, signed global component and energy identity terms,
   and declared run/feed events. Its current ledger is global rather than
   per-volume, and the report says so explicitly.
4. **Comparative reporting (implemented as a reusable report-layer API):**
   `compare_report_summaries` creates a versioned baseline/candidate comparison
   with KPI deltas, constraint changes, balance and numerical-health evidence.
   It preserves missing profile alignment as `NOT EVALUATED` rather than
   manufacturing a profile difference.

Every v2 field carries a data state where absence could otherwise look numeric:
`observed`, `derived`, `fallback`, `not_available`, `not_evaluated`, or
`not_applicable`. In particular, endpoint values are never silently used as a
time history. Old v1 summaries remain readable; their unavailable event,
balance, and controller evidence is displayed as unavailable rather than
reported as a passing assessment.

Controller performance is calculated from the complete accepted-step history
when present. The report identifies the controlled variable and shows final,
maximum absolute, mean absolute, integral absolute, overshoot, undershoot,
output range, and maximum output slew rate. Output saturation time is reported
only when explicit output bounds were persisted, and settling time only when an
explicit absolute-error settling tolerance was persisted; otherwise each is
shown as `NOT EVALUATED` rather than inferred from observed extrema.

Balance reporting retains the persisted signed ledger and adds a separate
summary for each component, total material, and energy where available.  It
reports the maximum absolute and normalized rate residual, accepted-step
trapezoidal integral of the absolute rate residual, final-60-second maximum,
and the time/location of the worst residual.  A PASS/FAIL balance assessment
is emitted only when a non-negative absolute and/or normalized tolerance is
explicitly persisted as `report_balance_tolerance` (or the legacy
`balance_tolerance`); otherwise the balance status remains `NOT EVALUATED`.

For Core V3 trajectories, the operating snapshot uses accepted-step feed flow
and top/bottom pressure histories. Declared feed temperature and pressure are
shown as configured conditions; they are not inferred from product or endpoint
values. Operating-limit tables include the observation time and location, and
structured event tables preserve before/after values, consequence, severity,
source component, and related gate when the event artifact provides them.

## Data Interpretation

The report labels true geometry-based vessel levels as percent. If a loop uses
or falls back to molar-holdup control, the report labels the controller PV in
`lbmol`; it does not misrepresent molar inventory as percent level. A report
marked `REVIEW` is an audit aid, not an accepted operating result.
