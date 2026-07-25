# DD-093 Core V3 Steady-Root Execution

- Classification: `dd093_execution_failed_before_scientific_decision`
- Decision: `retire_frozen_dd093_campaign_without_rerun`
- Contract commit: `a33749f`
- Authorized attempts: `1`
- Completed campaigns: `0`
- Process exit code: `1`

The frozen execution stopped during first-start report assembly. The scalar
`distillate` coordinate index was incorrectly accessed as a slice through
`layout.distillate.start`, raising `AttributeError` in
`movement_by_family()`.

The control-flow location shows that the first solve and its endpoint audits
had run, but no quantitative result was returned or serialized. Starts 2 and
3 did not run, so root existence, three-start reproducibility, and common-root
acceptance cannot be assessed.

Per the frozen contract, the campaign will not be patched and rerun. DD-092's
readiness result remains valid, but DD-093 establishes no accepted root and
authorizes no dynamic-DAE or integration work.
