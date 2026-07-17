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

## Data Interpretation

The report labels true geometry-based vessel levels as percent. If a loop uses
or falls back to molar-holdup control, the report labels the controller PV in
`lbmol`; it does not misrepresent molar inventory as percent level. A report
marked `REVIEW` is an audit aid, not an accepted operating result.
