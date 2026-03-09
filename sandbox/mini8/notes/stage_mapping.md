# 8-Stage Mapping (from 20-stage baseline)

File: `sandbox/mini8/input/distillation_column_template_8stage.xlsx`

Old -> New stage mapping:
- `1 -> 1`
- `2 -> 2`
- `5 -> 3`
- `9 -> 4`
- `12 -> 5` (feed)
- `16 -> 6`
- `18 -> 7`
- `20 -> 8`

Why this mapping:
- Keeps top boundary and stage-2 top-coupling behavior.
- Places feed near the middle (`new stage 5`) for rectifying/stripping representation.
- Retains lower-column instability region representation (`old 16..18`).
- Keeps reboiler boundary (`old 20`).

Other edits applied:
- `Number of Stages = 8`
- Streams stage indices: `Feed=5`, `Distillate=1`, `Bottom=8`
- Stage-geometry table reduced to three ranges:
  - `2..2` (upper transition tray)
  - `3..5` (rectifying/feed region)
  - `6..8` (lower/reboiler region)
