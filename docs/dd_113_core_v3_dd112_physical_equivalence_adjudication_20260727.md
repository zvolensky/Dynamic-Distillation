# DD-113 DD-112 Physical-Equivalence Adjudication Result

- Classification: `dd113_passed`
- Decision: `authorize_frozen_zero_time_initializer_audit`
- Canonical endpoint: `dd094_storage_and_pressure_profile`
- DD-112 evidence changed: `False`
- Live property calls: `0`
- Residual/Jacobian evaluations: `0/0`

## Decision

The two immutable DD-112 endpoints are physically equivalent under the
precommitted DD-113 engineering-variable ledger. All 15 comparison gates pass,
all inherited DD-112 gates other than `common_solution` remain unchanged and
true, and both reconstructed composition sets are strictly positive and
normalized.

DD-112 remains formally failed and is not rerun or reclassified. DD-113 accepts
the saved endpoint evidence prospectively and selects
`dd094_storage_and_pressure_profile` canonically because it has the lower final
objective. One separately frozen zero-time audit of that saved endpoint may now
be drafted. A timestep and dynamic integration remain unauthorized.

## Physical Comparison

| Metric | Observed | Limit | Result |
|---|---:|---:|---|
| Objective absolute difference | `1.211342e-11` | `1e-9` | Pass |
| Inventory scaled difference | `1.705538e-6` | `1e-5` | Pass |
| Liquid-composition absolute difference | `5.540258e-7` | `1e-6` | Pass |
| Lower-energy scaled difference | `1.550013e-7` | `1e-6` | Pass |
| Component-rate scaled difference | `4.805926e-7` | `1e-6` | Pass |
| Energy-rate scaled difference | `1.525632e-7` | `1e-6` | Pass |
| Pressure scaled difference | `5.563646e-9` | `1e-6` | Pass |
| Temperature absolute difference | `5.302651e-5 F` | `0.001 F` | Pass |
| Vapor-composition absolute difference | `4.843800e-7` | `1e-6` | Pass |
| Bubble-composition absolute difference | `8.794384e-9` | `1e-6` | Pass |
| Liquid-flow scaled difference | `1.401505e-7` | `1e-6` | Pass |
| Vapor-flow scaled difference | `2.562832e-7` | `1e-6` | Pass |
| Distillate scaled difference | `0` | `1e-6` | Pass |
| Bottoms scaled difference | `0` | `1e-6` | Pass |
| Condenser-duty scaled difference | `3.684885e-7` | `1e-6` | Pass |

## Provenance

- Source DD-112 result SHA-256:
  `b3a38cb9d2a0e78b95792d0fa4fb326787e17a4734921a14c490d1f5bf15bff1`
- Frozen DD-113 contract commit: `5d794bd`
- Source numerical evidence changed: `False`
- Preserved gates changed: `False`
- Property, residual, Jacobian, nonlinear-solve, initializer, timestep, and
  dynamic evaluations: `0`
