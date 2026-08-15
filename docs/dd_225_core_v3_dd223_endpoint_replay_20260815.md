# DD-225 DD-223 Endpoint Replay

## Purpose

DD-223 proved that the direct full-column steady-state solve failed, but its saved report did not include the individual residual values or complete Jacobian matrices needed to explain the failure. DD-225 replayed the two saved endpoints without changing them.

## Result

The replay passed every frozen gate:

- both exact 160-coordinate endpoints were evaluated;
- complete raw and scaled residual vectors were saved;
- complete `160 x 160` Jacobian matrices and singular vectors were saved at steps `1e-5` and `5e-6`;
- the DD-223 residual norms and singular spectra were reproduced with zero reported difference;
- all matrices retained rank 160;
- provider ownership passed;
- `12,474` logical provider calls completed in `6.169 s`;
- no nonlinear solve, state change, timestep, retry, or dynamic integration occurred.

## Meaning

The DD-223 failure is reproducible. It was not caused by missing output, a changed endpoint, or a one-time property calculation. The saved DD-225 matrices now permit a zero-call analysis of the weak equation and variable combinations.

DD-223 remains failed, and neither endpoint is an accepted initial condition. DD-225 authorizes only static conditioning localization from the saved evidence.
