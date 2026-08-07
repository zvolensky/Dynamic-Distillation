# DD-168 Seven-Volume Live Numerical Audit

## Verdict

**DD-168 passes every frozen gate.** The seven-volume Core V3 system is not
only structurally complete; it is numerically full rank, well inside the
declared conditioning limit, stable to finite-difference step halving,
physically evaluable, conservative, and provider-consistent at the frozen
source-mapped state.

No nonlinear solve, root acceptance, timestep, or integration occurred.

## Results

| Metric | Result | Limit |
|---|---:|---:|
| Unknowns/equations | `56 / 56` | Equal |
| Numerical rank at `1e-5` | `56` | `56` |
| Numerical rank at `5e-6` | `56` | `56` |
| Condenser local rank | `3 / 3` | `3 / 3` |
| Worst condition | `2.937784e6` | `<1e8` |
| Spectrum relative change | `1.063791e-7` | `<0.25` |
| Unexpected couplings | `0` | `0` |
| Zero rows/columns | `0 / 0` | `0 / 0` |
| Component telescoping | `1.145944e-16` | `<1e-12` |
| Energy telescoping | `3.404828e-17` | `<1e-10` |
| Condenser bubble residual | `1.776357e-15` | `<1e-10` |
| TP-flash vapor fraction | `4.459380e-4` | `<=1e-3` |
| Independent-PR temperature difference | `3.609037e-5 F` | `<1e-3 F` |
| Independent-PR vapor difference | `1.326779e-9` | `<1e-6` |
| Provider calls | `7,749` | `<20,000` |
| Wall clock | `6.082 s` | `<120 s` |

The condenser duty appears only in the reflux-drum energy equation. DWSIM
Peng-Robinson owns all governing fugacity, enthalpy, and density calls. TP flash
is diagnostic only, independent PR is validation only, and no fallback,
clipping, projection, or mixed-basis calculation occurs.

## Residual Interpretation

The frozen source-mapped point has a scaled residual infinity norm of
`0.397863`. This is diagnostic, not a failure: DD-168 did not attempt to create
or import a stationary root. The leading inconsistencies are Francis liquid
hydraulics and adjacent interior material balances, which is expected when a
larger reduced topology is populated directly from selected source-profile
locations without solving its balances.

The important result is that the residual has a complete, stable, full-rank
Jacobian at that point. A stationary solve is therefore a justified next test;
DD-168 does not claim in advance that the solve will converge or that a unique
physical root exists.

## Decision

One separately frozen seven-volume stationary-root campaign is authorized.
It should use the existing bounded transformed coordinates, DWSIM governing
properties, fixed scales and physical bounds, and more than one independently
constructed start. The contract must set common-root, residual, rank,
conditioning, conservation, physicality, provider, call, and wall gates before
execution.

Dynamic-DAE construction, initialization, timesteps, controllers, and
trajectories remain unauthorized until an accepted stationary root exists.

## Artifacts

- `logs/dd168_core_v3_seven_volume_numerical_contract_20260806.json`
- `logs/dd168_core_v3_seven_volume_numerical_20260806.json`
- `logs/dd168_core_v3_seven_volume_numerical_20260806.md`
- `tools/audit_core_v3_seven_volume_numerical.py`
