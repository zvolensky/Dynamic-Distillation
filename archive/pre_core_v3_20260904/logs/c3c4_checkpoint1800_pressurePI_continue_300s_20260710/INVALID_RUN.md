# Invalid Run - Do Not Continue

This 300 s pressure-control attempt is not a valid model result.

The Python environment did not contain `pythonnet`. The DWSIM provider object
was constructed, but every live tray flash failed and the model retained stale
thermo packets. Geometry-based level control also fell back to molar holdup.
The resulting pressure escalation and checkpoint must not be used for model or
controller conclusions.

The corrected live-DWSIM rerun is:

`logs/c3c4_checkpoint1800_pressurePI_continue_300s_r2_20260710`
