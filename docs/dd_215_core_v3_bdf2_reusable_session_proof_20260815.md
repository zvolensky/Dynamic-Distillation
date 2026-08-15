# DD-215 Reusable Production-Session Proof Result

- Classification: `reusable_production_session_proof_passed`
- Decision: `adopt_reusable_production_session_lifecycle`
- Completed roots: `24` / `24`
- Worst residual / condition: `5.644387e-12` / `3.172742e+07`
- Startup / trajectories / shutdown: `3.015` / `22.603` / `8.310 s`
- Total session wall: `33.929 s`
- Matrix count / logical calls: `69` / `84048`
- Intermediate shutdown observed: `False`
- Retry, tuning, alternate grid, or fallback: `False`

## Scientific Result

Both trajectories complete all `24/24` roots. Every root, shared-time physical,
response, worker, basis, provider, call, startup, shutdown, and session-wall
gate passes. Worst residual is `5.644387e-12`, worst condition is
`3.172742e+07`, and worst shared max/L1 inventory differences remain
`5.061785e-06/1.803949e-05 lbmol`. All eight DWSIM workers participate in every
Jacobian, and all 24 root epochs satisfy the once-per-worker basis lifecycle.

The session remains `started` after the coarse trajectory and before final
close. No intermediate shutdown occurs. It reaches `closed` only after the
explicit final close, which is measured once at `8.310 s`.

## Performance Meaning

DD-215 validates resource reuse; it does not claim faster nonlinear roots. The
two active trajectories consume `22.603 s`, while startup and final teardown
consume another `3.015 s` and `8.310 s`. Keeping the session open avoids paying
those lifecycle costs between continuation segments. The benefit grows when
many segments share one session, but final process teardown still exists and
must remain visible.

Future production reports shall separate:

- session startup wall time;
- each active trajectory-segment wall time;
- final worker shutdown wall time;
- complete session wall time.

DD-213 remains formally failed under its original all-in wall gate. DD-215 does
not reclassify it. Before another long live run, production qualification must
define whether its performance requirement applies to active segment latency,
complete session lifecycle, or both. No timing category may be silently
excluded after execution.
