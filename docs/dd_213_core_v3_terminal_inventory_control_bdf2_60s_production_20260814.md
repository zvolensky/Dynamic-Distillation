# DD-213 60-Second Production BDF2 Result

- Classification: `controlled_bdf2_60s_production_failed`
- Decision: `classify_60s_failure_before_further_integration`
- Completed roots: `720` / `720`
- Coarse/refined stop reasons: `None` / `None`
- Worst residual / condition: `9.633348e-12` / `3.172937e+07`
- Worst shared inventory max / L1: `5.061785e-06` / `1.803949e-05 lbmol`
- Matrix count / logical provider calls: `2100` / `2545478`
- Trajectory / governed wall: `276.857` / `308.084 s`
- Retry, tuning, alternate grid, or fallback: `False`

## Interpretation

DD-213 is a scientific pass and a formal production-performance failure. Both
the `240 x 0.25 s` and `480 x 0.125 s` paths completed, so the failure is not a
nonlinear stop, thermodynamic-provider failure, or physical divergence. Every
root, shared-time physical, response, worker, basis, provider, provider-call,
and startup gate passed. The sole failed campaign gate is governed wall time:
`308.084 s` against the frozen `<300 s` limit, an `8.084 s` (`2.69%`) overrun.

The complete run retains a worst residual of `9.633348e-12`, worst condition of
`3.172937e+07`, and worst shared max/L1 inventory differences of
`5.061785e-06/1.803949e-05 lbmol`. The coarse/refined total-response difference
is explained by external flow to `1.194855e-11 lbmol`. All 720 roots therefore
support the 60-second scientific-coherence conclusion.

## Performance Boundary

The nonlinear trajectories consume `276.857 s`; adjusted worker startup is
`3.144 s`, leaving approximately `28.083 s` in orchestration, evidence
assembly, serialization, and shutdown inside the governed total. Because all
roots completed before classification, the next authorized diagnostic should
be a zero-model-call timing and artifact-volume audit of this non-trajectory
overhead. DD-213 shall not be rerun, retuned, or reclassified, and longer
integration remains unauthorized.
