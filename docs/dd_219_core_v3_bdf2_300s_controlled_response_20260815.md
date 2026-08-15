# DD-219 Controlled-Response Adjudication Result

## Classification

`aborted_on_json_scalar_serialization`

DD-219 completed its zero-call static calculations but failed before writing a
result because one or more NumPy boolean scalars were passed to the standard
JSON encoder. No result artifact exists, so the response policy is neither
passed nor failed.

No DWSIM process, property call, residual, Jacobian, nonlinear solve, timestep,
endpoint regeneration, or trajectory rerun occurred. DD-218 retains its formal
response-only failure.

One separately numbered successor may change only result scalar coercion. It
must preserve the DD-219 source checksum, limits, calculations, gates, and
zero-call rule exactly.
