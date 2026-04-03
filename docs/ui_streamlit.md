# Streamlit UI

This repo now includes a thin Streamlit UI on top of the existing dynamic runner.

Launch:

```powershell
streamlit run ui/streamlit_app.py
```

More reliable on Windows from this repo:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_ui.ps1
```

Background launch with repo-local logs:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_ui.ps1 -Detached
```

Recommended install:

```powershell
pip install -e .[ui]
```

## Current UI Scope

- Select an existing Excel input workbook or upload a new `.xlsx`
- Enter `Run Name` and `Run Description`
- Start the existing runner as a subprocess
- Stop the active subprocess
- Launch either from a form or by pasting a runner CLI command:
  - CLI mode accepts bare flags or a full `python -m dynamic_distillation.dynamic_run_scaffold_v1 ...` command
  - if `--excel` is omitted in CLI mode, the selected/uploaded workbook is used
  - UI-managed logs stay enabled so the dashboard can keep following the run
- Optionally apply CLI-style execution overrides from the form UI:
  - runtime mode
  - thermo mode
  - thermo table path
  - thermo table anchor blend count
  - thermo pool workers/chunk size
  - thermo refresh cadence
  - fast startup
  - equilibrium-relaxation live PR
  - integrator
  - positive energy-mode override
- Watch live progress from the generated summary/profile CSV files
- View:
  - run progress/status
  - trend charts
  - latest stage profile table
  - a simple column schematic
  - warning lines from runner logs

## Design Notes

- The UI does not implement its own solver logic.
- It launches `python -m dynamic_distillation.dynamic_run_scaffold_v1`.
- In CLI mode, the UI normalizes the pasted command back onto that runner entry point.
- `tools/run_ui.ps1` launches Streamlit via `python -m streamlit` with `PYTHONPATH=src`.
- The UI passes workbook-derived `n_steps`, `dt`, and `log_every` explicitly.
- The UI emits an explicit `--thermo` mode in the command by default.
- `Include Energy` defaults to `On` in the UI because that matches the successful hydraulic-energy runs more closely.
- Precedence is:
  - UI advanced override
  - workbook-supported Excel setting
  - runner default
- Run metadata is persisted through:
  - `logs/**/run_metadata_<run_id>.json`
  - `logs/**/run_registry.csv`

## UI State Files

- The UI keeps its own lightweight working state under `.ui_state/`.
- Active run record:
  - `.ui_state/active_run.json`
  - this stores the current/most-recent run metadata the dashboard uses while a run is active or has just completed
  - it can include fields such as:
    - `pid`
    - `status`
    - `run_name`
    - `run_description`
    - `excel_path`
    - `logs_dir`
    - `command`
- Uploaded workbook cache:
  - `.ui_state/uploads/`
  - uploaded `.xlsx` files are copied here so the launched runner can use a stable local path
- These UI state files are distinct from the runner’s own per-run artifacts in `logs/**`.

## Current Limits

- The UI is aimed at local desktop use.
- Views are implemented as tabs rather than true desktop pop-up windows.
- Live refresh is polling-based.
- The schematic is intentionally simple in this first version.
- Startup status is shown once near the top of the dashboard, with compact
  milestone detail in the `Progress` tab.
