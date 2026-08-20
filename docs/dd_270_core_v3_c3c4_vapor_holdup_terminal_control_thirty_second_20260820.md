# DD-270 Thirty-Second Controlled Trajectory Result

## Decision

DD-270 aborted cleanly before endpoint 27 and shall not be rerun. A separately
frozen successor may correct the product-coordinate bound semantics without
changing controller tuning, equations, timestep, or solver settings.

## What happened

The saved DD-269 path replayed through `5.0 s`. Six new `0.25 s` roots then
converged through `6.5 s`. Every saved root remained physical, retained rank
`262`, and closed below `1.18e-12` scaled residual.

At the proposed `6.75 s` root, the bottoms controller predictor advanced its
cumulative product log coordinate from `0.0098642472` to `0.0102523456`. The
inherited absolute upper bound was `0.0100000000`, so SciPy correctly rejected
the initial guess before evaluating the root.

## Interpretation

This is not a column instability. The original tight product bound was suitable
for a short handoff test but, because the coordinate stores cumulative product
movement, it also imposed an unintended permanent limit of about one percent on
controller authority. The physical model was still converging cleanly when that
artificial limit was reached.

Final accepted values at `6.5 s`:

- Distillate: `2515.725911 lbmol/h`
- Bottoms: `4669.040455 lbmol/h`
- Reflux-drum level: `0.440779007`
- Bottom-sump level: `0.523285907`
- Residual: `9.917583e-13`
- Jacobian condition: `1.142666e7`

No retry, tolerance change, alternate grid, tuning change, fallback, or
post-abort property call occurred.
