**Thermo Surrogate Tables (PR-Based)**

This document describes the tabular thermo surrogate workflow in:
- `src/dynamic_distillation/thermo_surrogate_v1.py`
- `src/dynamic_distillation/thermo_table_pool_v1.py`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`

It covers both single-process table evaluation (`--thermo table`) and
process-pool table evaluation (`--thermo table-pool`).

---

**What This Solves**

Live PR flash across all stages can dominate runtime.
The surrogate workflow precomputes thermo surfaces and interpolates at runtime.

Tradeoff:
- Faster runs
- Some loss of fidelity vs full live EOS calls

---

**How Runtime Uses the Table**

At each thermo-refresh step, the RHS computes stage flashes from table data.
If the active provider implements `flash_TP_full_batch(...)`, the RHS uses batch mode.
Otherwise it falls back to stage-by-stage flash calls.

For `--thermo table-pool`:
- Stage flash rows are chunked and submitted to a process pool.
- Failed/timed-out chunk tasks fall back to local tabular evaluation.
- Scalar thermo calls (e.g., Cp/density helpers) use the local tabular provider.

---

**Interpolation Model**

Two interpolation layers:

1. Intra-anchor interpolation in `(T, P)`
- Bilinear interpolation on each anchor surface for:
  - `K(T,P,component)`
  - `HL(T,P)`
  - `HV(T,P)`
  - optional `Z(T,P)`, `rhoL(T,P)`

2. Inter-anchor interpolation in composition space
- Nearest anchors are blended with inverse-distance weights.
- `HL/HV/Z/rhoL`: linear weighted blend
- `K`: blend in `ln(K)` space, then exponentiate

Why `ln(K)` blending:
- Keeps `K > 0`
- Improves numerical stability for large volatility contrast

---

**Anchors**

An anchor is a reference composition vector `z_ref` with full `(T, P)` property surfaces.

Builder supports:
- Stage anchors from `x0[i,:]` (`include_stage_anchors=True`)
- Pure-component anchors `e_i` (`include_pure_anchors=True`)

---

**Build a Table**

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.thermo_surrogate_v1 `
  --excel distillation_column_template.xlsx `
  --out cache\thermo_table.json `
  --n-t 6 `
  --n-p 6 `
  --max-stage-anchors 6
```

Main builder options:
- `--n-t`, `--n-p`: grid density
- `--t-margin`, `--p-margin`: expand beyond case min/max
- `--max-stage-anchors`: subsample stage anchors
- `--no-stage-anchors`: disable stage anchors
- `--no-pure-anchors`: disable pure anchors
- `--no-rho`: skip liquid-density table
- `--verbose-backend`: print backend details while building

---

**Run With Single-Process Table Thermo**

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template.xlsx `
  --thermo table `
  --thermo-table cache\thermo_table.json
```

---

**Run With Parallel Table Thermo**

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template.xlsx `
  --thermo table-pool `
  --thermo-table cache\thermo_table.json `
  --thermo-pool-workers 6 `
  --thermo-pool-chunk-size 8 `
  --thermo-pool-timeout-sec 5
```

Pool tuning knobs:
- `--thermo-pool-workers`: worker count (`None` => `max(cpu_count-1,1)`)
- `--thermo-pool-chunk-size`: rows per submitted task (default `4`)
- `--thermo-pool-timeout-sec`: per-task timeout (optional)

---

**Table JSON Structure**

Top-level keys:
- `format_version`
- `created_at`
- `source`
- `excel_path`
- `components_excel`
- `components_dwsim`
- `n_components`
- `n_stages`
- `T_grid_F`
- `P_grid_psia`
- `anchors`
- `mw_lbm_per_lbmol` (optional)

Each `anchors[]` item:
- `name`
- `z_ref`
- `K` with shape `(nT, nP, Nc)`
- `HL_BTU_lbmol` with shape `(nT, nP)`
- `HV_BTU_lbmol` with shape `(nT, nP)`
- `Z` with shape `(nT, nP)` (optional)
- `rhoL_lbmol_ft3` with shape `(nT, nP)` (optional)

---

**Refresh Gating Interaction**

Runner thermo cadence and thresholds still apply in table modes:
- `--thermo-every`
- `--thermo-refresh-dt`
- `--thermo-refresh-dp`
- `--thermo-refresh-dx`

Stages below thresholds reuse cached thermo values.

---

**Accuracy / Maintenance Guidance**

Rebuild tables when any of these change materially:
- feed composition
- operating pressure profile
- expected tray temperature range
- component list/order

Practical guidance:
- Keep pure anchors enabled unless you have a specific reason to remove them.
- Expand margins and/or increase anchor density before increasing grid density aggressively.
- Runtime clips `T/P` to table bounds; extended out-of-range operation degrades fidelity.

---

**Troubleshooting**

- `thermo_mode='table' requires RunnerConfig.thermo_table_path`
  - Provide `--thermo-table <path>`.
- `thermo_mode='table-pool' requires RunnerConfig.thermo_table_path`
  - Provide `--thermo-table <path>`.
- Component mismatch errors
  - Table component ordering/names do not match case; rebuild table.
- Poor accuracy near edges
  - Add anchors, increase margins, or increase grid density.
