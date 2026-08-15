# DD-223 Full C3/C4 Stationary-Root Campaign

## Decision

DD-223 fails the frozen root, conditioning, spectrum, condenser-validation,
and common-root gates. The direct bounded least-squares path is stopped without
retry. Neither endpoint is an accepted root or dynamic initializer.

## Frozen Campaign

- System: 160 unknowns and 160 Core V3 steady equations.
- Starts: source-mapped DD-222 point and independent smooth topology state.
- Solver: bounded `least_squares(method="trf")`.
- Jacobian: 15-color central difference at `1e-5` during the solve and two
  endpoint steps at `1e-5` and `5e-6`.
- Governing properties: DWSIM Peng-Robinson.
- Prohibited: retry, continuation, alternate solver, tolerance/bound/scale
  adjustment, clipping, projection, fallback, timestep, and integration.

## Results

| Measure | Source start | Independent start | Required |
|---|---:|---:|---:|
| Function evaluations | 51 | 47 | <= 500 |
| Scaled residual infinity norm | 4.309924e-4 | 1.231733e-2 | < 1e-8 |
| Numerical rank | 160 | 160 | 160 |
| Worst Jacobian condition | 2.092644e10 | 2.445820e9 | < 1e8 |
| Spectrum relative change | 0.999827 | 0.998941 | < 0.25 |
| Active bounds | 0 | 0 | 0 |
| Physical state | pass | pass | pass |

The endpoints disagree by `9.127158e-2` on the frozen normalized physical
comparison, versus the required `<1e-7`. Both remain conservative and retain
positive flows, holdups, and compositions with ordered temperatures and
pressures. The failure is therefore not physical blow-up or rank loss.

## Diagnostic Endpoint

The source-start endpoint moves toward a plausible operating neighborhood:

- distillate: `2458.204650 lbmol/h`;
- bottoms: `4701.617902 lbmol/h`;
- condenser duty: `-50.290339 MMBTU/h`;
- top/bottom temperature: `119.440481 / 218.833257 F`.

These values are not accepted because the residual remains four orders of
magnitude above the gate, the Jacobian is ill-conditioned and step-sensitive,
and the second start does not reproduce the endpoint.

## Efficiency

The colored route succeeds as an implementation improvement. Each Jacobian
uses 30 residual evaluations instead of 320. The complete campaign uses
236,304 logical property calls in `50.383 s`, making the failure affordable and
decisive.

## Next Boundary

Do not launch DD-223 again or create a DD-224 variant that merely changes
starts, bounds, scales, tolerances, or least-squares settings. Permissible next
work is limited to static analysis of the immutable DD-223 evidence or a
separately justified solver architecture that directly addresses the observed
conditioning and basin dependence. Full-column dynamic integration remains
unauthorized.
