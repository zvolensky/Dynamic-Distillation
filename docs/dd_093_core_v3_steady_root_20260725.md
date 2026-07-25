# DD-093 Core V3 Steady-Root Execution Decision

Date: 2026-07-25

## Decision

The one authorized DD-093 execution failed before a scientific campaign
decision could be made. The frozen campaign is retired without rerun.

This is an implementation/reporting failure, not evidence that the Core V3
equations lack a root. It also is not a pass: only the first start reached
the post-solve reporting path, no quantitative endpoint was retained, and
Starts 2 and 3 were never attempted.

## Failure

The process exited with:

```text
AttributeError: 'int' object has no attribute 'start'
```

The frozen `movement_by_family()` reporter treated `layout.distillate`, a
scalar coordinate index, as though it were a slice:

```python
layout.distillate.start
```

The exception occurred while constructing the first `execute_start()` result,
after the solver, endpoint residual evaluation, and endpoint Jacobian audits
in the committed control flow. Those numerical values were not serialized.

## Interpretation

- Authorized execution attempts: one.
- Complete three-start campaigns: zero.
- First-start quantitative result retained: no.
- Starts 2 and 3 attempted: no.
- Common-root decision possible: no.
- Accepted Core V3 root established: no.
- Physical or numerical root failure established: no.
- Contract or solver implementation modified after execution: no.
- Rerun attempted: no.
- Dynamic integration attempted: no.

DD-092 remains a valid structural and live numerical-readiness pass. DD-093
does not advance the project beyond readiness because its frozen execution
could not produce the required evidence.

## Hard Stop

Do not patch the reporter and rerun DD-093. Do not change the solver,
tolerances, bounds, duties, pressures, provider, or starts. Do not import the
DD-088 root, draft the dynamic-DAE contract, or begin integration under this
campaign.
