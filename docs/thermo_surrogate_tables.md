**Thermo Surrogate Tables (PR-Based)**

This document describes the tabular thermo surrogate workflow added in `thermo_surrogate_v1`:

- Build thermo tables offline from Peng-Robinson flash calls.
- Run the dynamic simulation using `--thermo table` to avoid expensive live EOS calls at each step.

Files involved:

- Builder/provider module: `src/dynamic_distillation/thermo_surrogate_v1.py`
- Runner flag integration: `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- Lightweight runner integration: `src/dynamic_run_scaffold_v1.py`

---

**What Problem This Solves**

Live PR flash at every stage and step can dominate runtime.  
The surrogate table approach precomputes `K`, `HL`, `HV` (optional `Z`, `rhoL`) over `(T, P)` for representative compositions ("anchors"), then interpolates quickly at runtime.

Tradeoff:

- Faster simulation
- Some loss of thermodynamic fidelity versus live EOS

---

**How Interpolation Works**

Two interpolation layers are used:

1. Intra-anchor interpolation in `(T, P)`
- Bilinear interpolation on each anchor surface:
  - `K(T,P,component)`
  - `HL(T,P)`
  - `HV(T,P)`
  - optional `Z(T,P)`, `rhoL(T,P)`

2. Inter-anchor interpolation in composition space
- Compute distances from current composition `z` to each `z_ref`.
- Select nearest anchors and compute inverse-distance weights.
- Blend properties across anchors:
  - `HL/HV/Z/rhoL`: linear weighted blend
  - `K`: blend in `ln(K)` space, then exponentiate

Why `ln(K)` blending:
- Keeps `K > 0`
- More numerically stable for strong volatility contrast

---

**Anchors**

An anchor is a reference composition vector `z_ref` with full `(T, P)` property surfaces.

Builder supports:

- Stage anchors from `x0[i,:]` (`include_stage_anchors=True`)
- Pure-component anchors `e_i` (`include_pure_anchors=True`)

Pure anchors explicitly extend composition coverage to component fraction `1.0`.

---

**Build a Table**

Use the builder CLI:

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.thermo_surrogate_v1 `
  --excel distillation_column_template.xlsx `
  --out cache\thermo_table.json `
  --n-t 6 `
  --n-p 6 `
  --max-stage-anchors 6
```

Important options:

- `--n-t`, `--n-p`: grid density in temperature/pressure
- `--t-margin`, `--p-margin`: expansion beyond case min/max T,P
- `--max-stage-anchors`: subsample stage anchors for speed
- `--no-stage-anchors`: disable stage anchors
- `--no-pure-anchors`: disable pure anchors
- `--no-rho`: skip liquid density table

Practical note:
- Build time scales with `n_anchors * n_t * n_p` PR calls.
- Start with a smaller grid/anchor set, then refine.

---

**Run Using Table Thermo**

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template.xlsx `
  --thermo table `
  --thermo-table cache\thermo_table.json
```

Same option works for the lightweight runner:

```powershell
$env:PYTHONPATH='src'
python -m dynamic_run_scaffold_v1 `
  --excel distillation_column_template.xlsx `
  --thermo table `
  --thermo-table cache\thermo_table.json
```

---

**Current Example Table in This Repo**

Generated table:

- `cache/thermo_table.json`

Resulting coverage:

- `n_components = 3`
- `n_stages = 20`
- `n_anchors = 20` (stage anchors `stage_1` through `stage_20`)
- `T_grid_F` spans `95.556` to `243.772` (9 points)
- `P_grid_psia` spans `199.44` to `252.06` (9 points)
- `mw_lbm_per_lbmol` is included for hydraulic pressure-drop calculations

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
- `mw_lbm_per_lbmol` (optional component MW vector used by runners when available)

Each `anchors[]` item:

- `name`
- `z_ref`
- `K` with shape `(nT, nP, Nc)`
- `HL_BTU_lbmol` with shape `(nT, nP)`
- `HV_BTU_lbmol` with shape `(nT, nP)`
- `Z` with shape `(nT, nP)` (optional)
- `rhoL_lbmol_ft3` with shape `(nT, nP)` (optional)

---

**Accuracy / Maintenance Guidance**

- Rebuild tables when:
  - feed composition changes materially
  - operating pressure profile changes
  - expected tray temperature range changes
  - component set changes
- Use denser anchors first, then denser `(T,P)` grids.
- Keep pure anchors on unless there is a specific reason to remove them.
- Runtime interpolation clips `T` and `P` to grid bounds; if operation leaves the tabulated range, results may degrade.

---

**Troubleshooting**

- `thermo_mode='table' requires RunnerConfig.thermo_table_path`
  - Provide `--thermo-table <path>`.
- component mismatch errors
  - Table was built for a different component ordering; rebuild with current case.
- poor accuracy at extremes
  - Add anchors (especially near expected compositions), widen margins, or increase grid density.
