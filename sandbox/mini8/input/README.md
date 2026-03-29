# Seed Workbooks

Use these workbooks from `sandbox/mini8/input/` rather than editing root case files.

## Historical 20-stage Huang seed

- `distillation_column_template_20stage_huang_freep_900s_seed.xlsx`
- Kept only as archived project history from March 21, 2026

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

## Baseline source workbook

- `distillation_column_template_20stage_baseline.xlsx`
- Use this when you want the original 20-stage workbook rather than an archived historical endpoint

## Obsolete workbook

- `distillation_column_template_20stage_huang_900s_seed.xlsx`
- Do not use this file for new studies
- It was generated from the older invalid Huang branch that produced a near-flat tray pressure profile
