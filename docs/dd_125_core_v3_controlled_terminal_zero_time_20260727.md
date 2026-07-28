# DD-125 Core V3 Controlled-Terminal Zero-Time Abort

- Classification: `dd125_aborted_before_scientific_audit`
- Decision: `stop_controlled_terminal_dynamic_handoff`
- Cause: setpoint reconstruction used unsupported evaluation kind `preparation`
- Completed controlled-terminal residual, level reconstruction, or Jacobian: `False`
- Nonlinear solve, timestep, retry, or dynamics: `False`

DD-125 stopped at the provider-governed residual interface before returning a
controlled-terminal residual. It therefore supplies no evidence for or
against the physical controller architecture. In accordance with the frozen
DD-125 hard stop, no additional corrective successor or automatic retry is
authorized. DD-122 remains the accepted stationary zero-rate state and DD-123
remains a property-free structural controller result; dynamic controller
handoff remains unproven.
