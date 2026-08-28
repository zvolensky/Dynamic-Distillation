# DD-161 Core V3 Clapeyron Provider Qualification

## Decision


Clapeyron 0.6.26 can supply the direct imposed-phase fugacity coefficients
required by Core V3. This route does not depend on the ambiguous inactive row
returned by a stable single-phase TP flash. The adapter calls
`fugacity_coefficient(...; phase=:liquid/:vapor)` directly and rejects an
unknown phase rather than falling back to stable-phase evaluation.

## Upstream TP-Flash API Follow-Up (2026-08-20)

Clapeyron issue #608 now has a proposed API direction for separating phase
slots from active phases: `numphases(result)`,
`numphases(result, true)`, `is_active_phase`, and the lazy iterator
`each_active_phase_index(result)`. The maintainer also identified
`merge_duplicate_phases!(result, ignore_zeros=false)` as the cleanup operation
for distinguishing a retained converged incipient phase from a duplicate
zero-fraction phase. A retained inactive composition is useful only in the
former case; when duplicate merging removes it, no discarded K-value is
available and callers must extrapolate separately.

This does not change the DD-161 qualification decision. After the release,
the required work is limited to the Clapeyron adapter and focused compatibility
tests, including the experimental `tp_flash2` batch helper. Core V3 governing
equations and provider call-audit permissions remain unchanged. Discarded
K-values describe a non-active phase and must remain diagnostic unless a
separate model decision authorizes their use in runtime equilibrium targets.

## Release Adoption Contract

When a release containing the issue #608 changes is available, adoption shall
be handled at the Clapeyron adapter boundary:

1. Use `numphases(result, true)` or `each_active_phase_index(result)` rather
	than the number of composition rows to identify active phases.
2. Apply `merge_duplicate_phases!(result, ignore_zeros=false)` and distinguish
	a retained converged incipient phase from a removed duplicate phase.
3. Keep the one-active-phase/no-incipient-phase case explicit; do not create
	a physical vapor composition or K-values from a duplicate row.
4. Update and test the experimental `tp_flash2` batch helper before enabling it.
5. Leave Core V3 governing equations, state variables, and provider call-audit
	permissions unchanged.
6. Treat retained incipient/discarded K-values as diagnostic until a separate
	residual, trajectory, and scientific-difference study authorizes runtime use.

This is an adapter compatibility update, not a Core V3 model-equation update.

## Release Verification (2026-08-28)

Clapeyron 0.6.27 implements the anticipated active-phase API and retained
inactive composition behavior.  DD-275 verified the published Issue #608
state and the original 54-call frozen campaign.  All 54 calls completed with
zero unit-K results: 44 were explicitly labeled retained inactive-phase
estimates and 10 were true two-active-phase equilibrium results.  Scalar and
batch-style diagnostic calls agreed exactly.

The adapter exposes this data through a diagnostic-only method.  The strict
runtime TP-flash path continues to reject a one-active-phase state as lacking
a physical equilibrium phase pair.  This preserves the DD-161 property
qualification and does not expand Core V3 provider permissions.  See
`docs/dd_275_clapeyron_0627_inactive_phase_regression_20260828.md`.

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
