# DD-135 DD-134 Globalization Audit Result

- Classification: `audit_invalid`
- Decision: `stop_pending_audit_integrity_review`
- coarse stalled residual: `8.499349302e-09`
- coarse stale/fresh accepted fractions: `[1.0, 0.5, 0.25, 0.125]` / `[1.0, 0.5, 0.25, 0.125]`
- coarse fresh best residual: `1.943352921e-12`
- coarse Jacobian relative drift: `1.256284476e-05`
- refined stalled residual: `4.731911069e-08`
- refined stale/fresh accepted fractions: `[1.0, 0.5, 0.25, 0.125]` / `[1.0, 0.5, 0.25, 0.125]`
- refined fresh best residual: `2.106526421e-10`
- refined Jacobian relative drift: `7.510739691e-06`
- DWSIM calls: `5209`
- Wall clock: `2.461 s`

No solve was accepted and no state, timestep, or trajectory advanced.

## Interpretation

The audit is invalid because the shortened fresh-process reconstruction does not reproduce either saved DD-134 stalled residual. The coarse value changes from `5.091822047e-8` to `8.499349302e-9`; the refined value changes from `1.579972595e-8` to `4.731911069e-8`. The rebuilt stale-Jacobian conditions also differ by `6.811644e-4` and `1.071336e-3` relative, above the frozen `1e-6` limit.

All four reconstructed Jacobians remain rank `50/50`, provider provenance passes, and both reconstructed stale and fresh directions accept every trial fraction. Those line-search results cannot adjudicate DD-134 because they apply to numerically different reconstructed roots.

DD-134 remains unchanged and retired. No adaptive-refresh solver is authorized. The next defensible work is a separately frozen residual/provider replay audit that records same-point repeatability and the process/call-order state needed for a reproducible failure artifact.
