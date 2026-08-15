# DD-221 Full C3/C4 Structural Migration

## Result

`full_c3c4_structural_migration_passed`

The accepted Core V3 architecture maps generically onto the actual C3/C4
source topology:

- 20 physical source stages;
- reflux drum at stage 1;
- 10 rectifying volumes at stages 2 through 11;
- feed volume at stage 12;
- 7 stripping volumes at stages 13 through 19;
- combined reboiler/sump at stage 20;
- n-propane, n-butane, and n-pentane components.

The source workbook is
`distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx`
with SHA-256
`6b7932cdf67c352baeab5bf7b791fea6cd87039dc38524782b3458f17d811955`.
Its profile is a source mapping and audit point, not an accepted Core V3 root.

## Structural Gates

| Layer | Equations / unknowns | Structural rank | Result |
|---|---:|---:|---|
| Provider-governed steady registry | 160 | 160 | Pass |
| Dynamic DAE | 158 | 158 | Pass |
| Terminal-controlled DAE | 162 | 162 | Pass |
| Constant-step controlled BDF2 | 162 | 162 | Pass |

The BDF2 contract owns 164 history values. Component and energy conservation
remain exact by construction, all 20 source stages map once, and no equation
owner refers to a hard-coded source-stage number.

## Scaling Defect Resolved

SciPy's structural-rank matcher stalled for minutes on the full `160 x 160`
incidence pattern even though the smaller accepted systems were fast. Core V3
structural audits now use a deterministic Hopcroft-Karp matcher. Regression
tests reproduce SciPy's rank on smaller full-rank, deficient, square, and
rectangular patterns. The complete DD-221 audit now takes about two seconds.
This changes audit implementation only; no equation, residual, property, or
dynamic calculation changes.

## Boundary

DD-221 starts no DWSIM process and makes no property, residual, Jacobian,
nonlinear-solve, timestep, or trajectory call. It proves that scaling does not
create a structural degree-of-freedom defect. It does not prove that the raw
workbook profile is a consistent root or that a practical full-column root is
reachable.

The next permitted milestone is one separately frozen source-mapping and live
residual/Jacobian readiness audit. A nonlinear root solve and full-column
dynamic integration remain unauthorized until that audit passes.
