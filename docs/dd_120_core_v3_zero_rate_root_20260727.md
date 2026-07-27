# DD-120 Core V3 Zero-Rate Root Campaign

- Classification: `dd120_failed`
- Decision: `retire_terminal_scaled_zero_rate_root_path`
- Wall clock: `14.660 s`
- DWSIM calls: `32481`
- Final residual infinity norms: `[0.002448575533219474, 0.002448575531789994]`
- Common-root difference: `1.351493e-09`
- Least-squares costs: `[2.944273736882e-5, 2.944273736883e-5]`
- Left-null residual projection: `0.007673687167`
- Terminal residuals: below `7.04e-12` scaled
- Failed gate: `residual` only

## Interpretation

Both frozen starts terminate successfully at the same stationary, interior, physical endpoint. All terminal-holdup, common-root, optimality, rank, condition, spectrum, coloring, bounds, pressure, conservation, provider, call, and wall gates pass. The unchanged DAE rows retain a residual floor of `2.4486e-3`, more than five orders of magnitude above the frozen `1e-8` limit.

This is direct evidence that the inherited drum and sump holdups are not exactly compatible with a zero-rate root of the present DAE under the frozen operating specifications. The converged endpoint preserves the terminal totals but shifts the released whole-column targets by approximately `[-43.146, +21.636, +21.263] lbmol` and `-120405 BTU`; those are diagnostics, not the cause of the formal failure.

DD-120 performed no timestep or dynamics. The terminal-scaled zero-rate root path is retired without retry, target adjustment, alternate solver, or continuation. A distinct DAE-only feasibility study would require a new contract and must explicitly treat the two near-null terminal inventory scales rather than silently retuning these targets.
