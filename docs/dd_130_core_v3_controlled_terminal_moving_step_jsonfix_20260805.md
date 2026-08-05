# DD-130 Core V3 Controlled-Terminal Moving-Step Result

- Classification: `dd130_failed`
- Decision: `stop_controlled_terminal_dynamic_handoff`
- Distillate change: `-2.365456e-04` relative
- Bottoms change: `-4.195741e-03` relative
- Terminal accumulation: `[0.734610844602912, 20.308717430464185]` lbmol/h
- Worst refinement metric: `2.565702e-06`
- Jacobian ranks: `[50, 50]`
- Worst condition: `2.085460e+05`
- DWSIM calls: `24165`
- Wall clock: `10.220 s`

DD-130 changed only JSON boolean coercion relative to DD-129. No retry, tuning, or trajectory was attempted.

## Decision Detail

Every scientific and physical gate passed. The sole formal failure is the
precommitted provider-call limit: `24,165` actual calls versus `<16,000`.
Therefore the moving step is numerically successful but not accepted under the
frozen DD-130 contract, and no trajectory is authorized.

## Efficiency Diagnosis

- Jacobian evaluations: `23,520` calls (`97.3%` of all calls)
- Residual evaluations: `644` calls
- Provider preparation: `1` call
- Nonlinear iterations/Jacobians: `7` coarse, `7` first half-step, `5` second half-step
- Property calls per complete residual evaluation: exactly `28`

The provider residual path is already compact. The dominant cost is rebuilding
a 21-color central-difference Jacobian at every trust-region iteration. The
next admissible engineering study is a zero-call solver-efficiency design for
modified Newton/Jacobian reuse. It must not rerun DD-130 or begin a trajectory.
