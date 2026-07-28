# DD-124 Core V3 Controlled-Terminal Zero-Time Abort

- Classification: `dd124_aborted_before_audit`
- Decision: `retire_dd124_contract_without_scientific_result`
- Cause: shared context keyword `pressure_numerical` did not match kernel keyword `numerical`
- Governed residual, level reconstruction, or Jacobian: `False`
- Nonlinear solve, timestep, retry, or dynamics: `False`

DD-124 stopped before its first controlled-terminal residual evaluation. It
therefore provides no evidence for or against the physical or numerical
handoff. The frozen DD-124 contract shall not be rerun. A separately frozen
successor may correct only the keyword mapping while retaining the exact
state, geometry, controller memories, gates, finite-difference steps, and
efficiency limits.
