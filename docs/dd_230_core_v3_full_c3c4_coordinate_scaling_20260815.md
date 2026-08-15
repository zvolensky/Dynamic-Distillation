# DD-230 Full-C3/C4 Fixed Coordinate Scaling

## Method

DD-230 reads the four complete DD-229 Jacobians. For every coordinate, it computes the geometric mean of that column's norm across both endpoints and both finite-difference steps. The fixed solver scale is the inverse of that aggregate norm, normalized to a geometric mean of one.

No individual endpoint, stage, residual row, or desired solution is favored.

## Result

- The 160 scales span only `8.813:1`.
- Every matrix condition improves.
- The independent-endpoint conditions fall from about `4.02e5` to `2.05e5`.
- The source-endpoint conditions fall from about `3.36e6` to `1.86e6`.
- Improvements are `1.80-1.96x`.
- All scaled conditions remain well below the established `1e8` limit.
- No model, provider, solver, timestep, or integration call occurs.

## Decision

One frozen stationary-root campaign is authorized using:

- the two exact DD-223 endpoints as independent starting guesses;
- DWSIM imposed-phase fugacity and phase enthalpy;
- parameter-aligned PR liquid density from the smallest positive root;
- the fixed 160-coordinate DD-230 scale;
- the existing residual scales, physical bounds, 15-color Jacobian, solver, and acceptance gates.

No tuning, retry, continuation, timestep, or dynamics is authorized.
