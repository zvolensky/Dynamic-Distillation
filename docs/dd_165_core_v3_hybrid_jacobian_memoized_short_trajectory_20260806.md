# DD-165 Hybrid-Jacobian Memoized Short-Trajectory Abort

- Classification: `integration_aborted_before_scientific_result`
- Decision: `authorize_exact_memoization_api_correction_and_separately_frozen_successor`
- Failure: `ThermoClapeyronProviderV1` did not implement the exact-state
  memoization statistics API required by the existing worker accounting.
- Location: first coarse-root worker Jacobian, before a Newton correction.
- Root accepted or state advanced: `false`

The abort is an integration-contract finding, not a trajectory failure. The
hybrid wrapper correctly refused to report DWSIM-only memo statistics as if
they covered Clapeyron fugacity calls. A disabled-by-default exact-key
fugacity cache and statistics API may be implemented, tested, and exercised
only under a separately frozen successor. DD-165 itself will not be rerun.
