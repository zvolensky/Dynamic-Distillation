# Seed Workbooks

Use these workbooks from `sandbox/mini8/input/` rather than editing root case files.

## Recommended 20-stage seed

- `distillation_column_template_20stage_huang_freep_900s_seed.xlsx`
- Source: corrected Huang `900 s` steady-state run from March 21, 2026
- Intended use: 20-stage feed-disturbance studies from a physically graded Huang steady state

Example run pattern:

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel sandbox\mini8\input\distillation_column_template_20stage_huang_freep_900s_seed.xlsx `
  --runtime-mode huang `
  --huang-top-drum-vapor-relaxation-sec 10 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --condenser-duty-mode specified `
  --condenser-duty-btuph -49640000 `
  --n-steps 900 `
  --dt 0.2 `
  --log-every 150 `
  --logs-dir logs\case20_huang_freep_disturbance_seed `
  --allow-repeat-command
```

## Baseline source workbook

- `distillation_column_template_20stage_baseline.xlsx`
- Use this when you want the original 20-stage workbook rather than a restarted Huang endpoint

## Obsolete workbook

- `distillation_column_template_20stage_huang_900s_seed.xlsx`
- Do not use this file for new studies
- It was generated from the older invalid Huang branch that produced a near-flat tray pressure profile
