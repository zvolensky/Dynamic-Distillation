# DD-216 Core V3 Production-Session Timing Policy

## Decision

The property-free timing-policy implementation passes. Production performance
can now be accepted or rejected without conflating active simulation work with
worker startup and shutdown, and without dropping any interval from the total.

## Executable Policy

`assess_production_session_timing` independently evaluates:

- exact ordered segment-name contract;
- completion and wall limit for every named segment;
- sum of all active segments;
- agreement between segment sum and session active time;
- startup wall time;
- presence and wall time of final shutdown;
- presence and wall time of the complete session;
- unattributed wall time after startup, active work, and shutdown are summed.

Every observed duration must be finite and nonnegative. Limits must be finite,
unambiguous, and frozen before the live work they govern. Segment limits use
unique names, so a result cannot pass by relabeling or reordering trajectories.

## DD-215 Static Assessment

The saved DD-215 evidence is assessed with zero DWSIM, property, residual,
Jacobian, solver, or timestep calls. The static limits are:

| Timing block | Frozen limit | Observed |
|---|---:|---:|
| Startup | `5.0 s` | `3.015291 s` |
| `dd215_coarse` | `20.0 s` | `15.817244 s` |
| `dd215_refined` | `10.0 s` | `6.785416 s` |
| All active segments | `25.0 s` | `22.602660 s` |
| Final shutdown | `10.0 s` | `8.309981 s` |
| Complete session | `40.0 s` | `33.928759 s` |
| Unattributed overhead | `0.1 s` | `0.000827 s` |

All independent gates pass. The identity check proves that startup, the two
active paths, shutdown, and less than one millisecond of orchestration explain
the complete measured session.

## Tests And Scope

Seven timing-policy tests cover the saved passing evidence and independent
failures for a slow segment, excessive complete-session wall, open-session
missing values, reordered names, active-time mismatch, hidden overhead, and
invalid contracts. Together with the reusable-session lifecycle tests, 14
focused tests pass.

DD-216 changes no model equation, provider, Jacobian, nonlinear solver,
controller, timestep, or accepted state. It makes no live call.

## Next Boundary

One separately frozen single-grid production-segment qualification may now be
designed. It must state before execution:

- the selected already-qualified BDF2 grid and duration;
- active segment wall limit;
- startup, shutdown, and complete-session limits;
- maximum unattributed overhead;
- all inherited scientific and provider gates.

The earlier two-grid campaigns remain validation evidence. A production run
shall not repeat the refined path merely to satisfy performance accounting.
Longer or unrestricted integration remains unauthorized.
