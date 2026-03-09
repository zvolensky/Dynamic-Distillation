# Mini8 Sandbox

Purpose: isolated workspace for reduced-stage troubleshooting so root case files remain untouched.

## Folder layout
- `input/`:
  - `distillation_column_template_20stage_baseline.xlsx` = copied baseline source.
  - place derived mini-column workbook(s) here (for example: `distillation_column_template_8stage.xlsx`).
- `runs/`:
  - keep run artifacts/log exports for mini-column studies only.
- `notes/`:
  - keep assumptions, tray mapping, and tuning notes for the mini model.

## Working rule
- Do not edit root workbook(s) while testing mini-column ideas.
- Always run with `--excel sandbox/mini8/input/<file>.xlsx`.
