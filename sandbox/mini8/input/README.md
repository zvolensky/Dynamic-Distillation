# Seed Workbooks

Use these workbooks from `sandbox/mini8/input/` rather than editing root case files.

## Recommended 20-stage seed

- `distillation_column_template_20stage_huang_freep_900s_seed.xlsx`
- Source: corrected Huang `900 s` steady-state run from March 21, 2026
- Intended use: 20-stage feed-disturbance studies from a physically graded Huang steady state

## Recommended 20-stage ChemSep parity seed

- `distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx`
- Source: rebuilt directly from `ChemSep Depropanizer_warmer_feed.xls`
- Intended use: 20-stage hydraulic-energy parity/debug runs against the warmer-feed ChemSep case

Current best matching hydraulic branch for this seed:
- `runtime-mode hydraulic`
- `include-energy`
- `equilibrium-relaxation-mode phase-holdup`
- condenser-duty pressure control to `top-pressure-sp = 220.44 psia`

Important note:
- in the current hydraulic parity branch, `L_out_used` is still the active liquid profile
- `L_out_hyd` is logged as a hydraulic diagnostic and should not be interpreted as the governing tray liquid flow unless liquid-hydraulic override is explicitly enabled

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
