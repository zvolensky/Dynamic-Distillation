Archived root-level workbooks that are no longer the active simulation input.

Purpose:
- keep the repo root focused on the current chemsep workbook
- reduce accidental edits to stale restart/template files
- make version-control diffs easier to interpret

Active root workbook:
- `distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx`

Notes:
- sandbox input workbooks were left in place because some are still referenced by docs and scripts
- restart workbooks produced by runs should continue to live with their run artifacts in `logs/`
