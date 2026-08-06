# DD-161 Core V3 Clapeyron Provider Qualification

## Decision

- Classification: `clapeyron_fugacity_authority_qualified_only`
- Decision: `authorize_fugacity_acceleration_design_only`
- Full provider substitution: **not authorized**
- Nonlinear solve, timestep, or trajectory: **not attempted**

Clapeyron 0.6.26 can supply the direct imposed-phase fugacity coefficients
required by Core V3. This route does not depend on the ambiguous inactive row
returned by a stable single-phase TP flash. The adapter calls
`fugacity_coefficient(...; phase=:liquid/:vapor)` directly and rejects an
unknown phase rather than falling back to stable-phase evaluation.

## Fixed-State Comparison

The live comparison used the accepted DD-160 five-volume state and injected
DWSIM PR critical constants, molecular weights, acentric factors, and binary
interaction parameters into Clapeyron PR.

| Quantity | Worst difference | Result |
|---|---:|---|
| Liquid fugacity coefficient | `6.4410e-5` absolute | Pass |
| Vapor fugacity coefficient | `1.8452e-7` absolute | Pass |
| Molecular weight | `1.4211e-14 lbm/lbmol` | Pass |
| Repeated liquid fugacity | `0.0` absolute | Pass |
| Vapor compressibility | `0.366%` relative | Diagnostic |
| Liquid density | `7.445%` relative | Not drop-in equivalent |
| Latent enthalpy | `172.946 BTU/lbmol` | Not drop-in equivalent |

The fugacity match is sufficient to justify a bounded acceleration design.
The density and caloric differences mean that replacing every DWSIM property
call would change Francis hydraulics and energy balances. That is a scientific
model change, not a performance-only change.

## Performance

Fifty neighboring 28-call Core V3 property packets were evaluated after
startup and compilation:

- DWSIM: `1.117091 s`
- Clapeyron: `0.120901 s`
- Warm packet speedup: `9.2397x`

Fresh-process costs remain material: DWSIM parameter extraction took about
`10.10 s`, and Clapeyron model construction took about `14.33 s`. These costs
are amortized in a sustained solve but matter for short probes and worker
creation. The existing persistent-process architecture is therefore still
appropriate.

## Implementation

The optional provider now exposes strict imposed-phase fugacity coefficients,
declared phase properties, component molecular weights, explicit
`clapeyron.*` provenance, and a provider-neutral Core V3 structural registry.
DWSIM remains the default, so historical contracts and results are unchanged.

## Authorized Next Step

One separately frozen **hybrid fugacity benchmark** may replace only governing
direct-fugacity calls with parameter-aligned Clapeyron while retaining DWSIM
enthalpy, density, molecular-weight, TP-flash diagnostic, and accepted model
equations. It must compare a saved full residual and colored Jacobian against
the DWSIM baseline, retain rank and conditioning, and quantify end-to-end wall
improvement under a prospective scientific difference limit.

No root solve or trajectory should use the hybrid provider until that bounded
residual/Jacobian study passes.

Evidence: `logs/dd161_core_v3_clapeyron_provider_qualification_20260806.json`.
Reproduction: `python tools/qualify_core_v3_clapeyron_provider.py`.
