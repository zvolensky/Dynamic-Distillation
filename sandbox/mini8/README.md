# Mini8 Sandbox

Purpose: isolated workspace for reduced-stage troubleshooting so root case files remain untouched.

## Folder layout
- `input/`:
  - `distillation_column_template_20stage_baseline.xlsx` = copied baseline source.
  - `distillation_column_template_20stage_huang_freep_900s_seed.xlsx` = corrected steady Huang seed for 20-stage disturbance studies.
  - place derived mini-column workbook(s) here (for example: `distillation_column_template_8stage.xlsx`).
- `runs/`:
  - keep run artifacts/log exports for mini-column studies only.
- `notes/`:
  - keep assumptions, tray mapping, and tuning notes for the mini model.

## Working rule
- Do not edit root workbook(s) while testing mini-column ideas.
- Always run with `--excel sandbox/mini8/input/<file>.xlsx`.

## UV prototype
- Entry point: `python -m dynamic_distillation.uv_flash_sandbox_v1`
- Default workbook: `sandbox/mini8/input/distillation_column_template_8stage.xlsx`
- Recommended first run:
  - `python -m dynamic_distillation.uv_flash_sandbox_v1 --thermo table --thermo-table cache\thermo_table.json --n-steps 20 --dt 0.2 --liquid-flow-mode francis --vapor-flow-mode conductance`
- Outputs:
  - `sandbox/mini8/runs/uv_flash_summary_<run_id>.csv`
  - `sandbox/mini8/runs/uv_flash_profile_<run_id>.csv`
  - `sandbox/mini8/runs/uv_flash_compare_metrics_<run_id>.csv` when `--compare-ref-profile` is supplied
  - `sandbox/mini8/runs/uv_flash_compare_detail_<run_id>.csv` when `--compare-ref-profile` is supplied

Current scope:
- Internal trays (`stages 2..7`) use stage-level UV solves.
- Distillate-drum and bottoms-sump liquid holdups are dynamic inventories.
- Distillate-drum and bottoms-sump now also carry dynamic energy states, so their temperatures are solved from `(U, P, x)` instead of being pinned to workbook references.
- For total condensers, the top-node energy balance now includes the workbook condenser duty explicitly, so the condenser/drum temperature is duty-driven rather than only flow-driven.
- Internal liquid traffic can use `--liquid-flow-mode profile`, `--liquid-flow-mode francis`, or `--liquid-flow-mode holdup-tau`.
- Internal vapor traffic can use either `--vapor-flow-mode profile` or the default `--vapor-flow-mode conductance`.
- The conductance vapor closure consumes the Francis-weir liquid head when hydraulic liquid mode is enabled.
- The `holdup-tau` liquid mode computes tray liquid outflow from tray liquid holdup divided by a hydraulic time constant, while pressure/vapor updates remain partitioned.
- For total condensers, stage 1 is modeled as a condenser boundary block rather than a dynamic UV tray.
- The condenser block condenses stage-2 vapor to a bubble-point liquid at `P_stage2 - condenser_dp` and routes that liquid directly to the reflux drum.
- Stage 8 is modeled as a partial-reboiler boundary block tied to the bottoms-sump liquid state rather than a dynamic UV tray.
- The reboiler block flashes sump liquid at the bottom-end pressure anchor, returns boilup vapor to stage 7, and removes that vapor directly from the sump inventory.

Historical Huang notes and seed files remain only as archived project history.

## Equilibrium-DAE v2 reuse policy

DD-078 authorizes selective reuse of this sandbox for the new `core_v2`
architecture.

Reusable inputs and patterns:
- the compact workbook and existing Excel-loading path;
- component, stream, terminal, pressure, temperature, and geometry data;
- UV state-building and terminal liquid-node patterns;
- simultaneous-layout and Jacobian-conditioning audit patterns.

Not reusable as v2 governing physics or acceptance evidence:
- the sampled 20-stage profile as an independently known solution;
- historical mini8 trajectories;
- profile-owned flow closures;
- clipping, explicit-Euler advancement, anchor regularization, or legacy
  equation ownership.

Mini8 may seed later Gate B and Gate C studies. The accepted answer must still
come from the new equations and an independent reference or conservation gate.

Reference comparison:
- Example against the existing mini8 parity baseline:
  - `python -m dynamic_distillation.uv_flash_sandbox_v1 --thermo table --thermo-table cache\thermo_table.json --n-steps 20 --dt 0.2 --liquid-flow-mode francis --vapor-flow-mode conductance --compare-ref-profile logs\column_profile_20260228_100313.csv`

## Simultaneous UV pilot
- Entry point: `python -m dynamic_distillation.uv_flash_sandbox_simultaneous_v1`
- Recommended first run:
  - `set PYTHONPATH=src`
  - `python -m dynamic_distillation.uv_flash_sandbox_simultaneous_v1 --thermo table --thermo-table cache\thermo_table.json --n-steps 2 --dt 0.2 --compare-ref-profile logs\column_profile_20260228_100313.csv`
- Outputs:
  - `sandbox/mini8/runs/uv_flash_simul_summary_<run_id>.csv`
  - `sandbox/mini8/runs/uv_flash_simul_profile_<run_id>.csv`
  - `sandbox/mini8/runs/uv_flash_compare_metrics_simul_<run_id>.csv` when `--compare-ref-profile` is supplied
- Current scope:
  - Active tray `T/P/beta`, top-node `T`, bottom-node `T`, and full internal `L/V` vectors are solved together in one Newton loop at each step.
  - Differential states still advance with explicit Euler after the algebraic solve, so this is a simultaneous algebraic pilot, not yet a full implicit column DAE integrator.
  - The pilot now uses adaptive vapor continuation, adaptive timestep retry, and outer state-update backtracking before a bad step is accepted.
  - Experimental vapor residual regularization is available via `--vapor-regularization-weight`; this adds a soft penalty that keeps the vapor algebraic block closer to its anchor state to improve conditioning.
  - `uv_flash_simul_summary_<run_id>.csv` includes `simultaneous_state_update_relax` so you can see when the outer explicit update had to be damped.
  - Short runs now solve successfully for the first few steps, but the current pilot is not yet robust over longer horizons.
