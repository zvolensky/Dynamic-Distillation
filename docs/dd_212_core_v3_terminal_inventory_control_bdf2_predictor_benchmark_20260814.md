# DD-212 BDF2 Linear-Predictor Benchmark Result

- Classification: `controlled_bdf2_linear_predictor_passed`
- Decision: `adopt_linear_extrapolation_bdf2_initial_guess`
- Baseline/predictor trajectory wall: `24.007053` / `18.844021 s`
- Predictor speedup: `1.274x`
- Baseline/predictor matrices: `142` / `114`
- Matrix/call reductions: `19.718%` / `18.988%`
- Maximum accepted-science difference: `3.046807e-10`
- Governed wall: `64.555 s`
- Retry, tuning, alternate predictor, or fallback: `False`

## Evidence

- Both paths completed all `40 x 0.25 s` roots.
- Every root passed residual, rank, condition, physicality, equilibrium,
  conservation, controller, response, worker, and provider gates.
- Baseline/predictor logical provider calls: `171,360/138,822`.
- Baseline/predictor adjusted startup wall: `2.389891/2.497770 s`.
- Every Jacobian used all eight workers and every root rebuilt eight worker
  bases exactly once.
- Provider fallback attempted: `False`.
- The accepted-science objects are not bit-for-bit equal because the nonlinear
  paths differ, but their maximum numeric difference is `3.046807e-10`, below
  the prospective `1e-9` engineering-equivalence limit.

## Decision

`linear_extrapolation` is adopted for production controlled BDF2 launches. The
library default remains `accepted_endpoint` for backward compatibility and
historical replay; production recipes must select the accepted predictor
explicitly. No extrapolation factor, clipping, projection, or fallback is
introduced.

The predictor reduces the typical Jacobian burden rather than changing its
unit cost. Combined with DD-210's `1.535x` worker scaling, the measured short-run
improvement is approximately `1.96x`. Applying that factor to DD-209 projects
about `112 s` trajectory wall for the same two 30-second paths and about `224 s`
for two 60-second paths before startup/shutdown and reporting. This supports
one separately frozen 60-second production milestone using eight workers and
the explicit predictor. It does not authorize Jacobian reuse, derivative
changes, or unrestricted duration.
