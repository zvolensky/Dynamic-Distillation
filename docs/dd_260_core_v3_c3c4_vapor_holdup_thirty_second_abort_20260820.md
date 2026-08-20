# DD-260 Thirty-Second Vapor-Holdup Abort

- Classification: `recovery_atomic_replace_abort`
- Decision: preserve endpoint 81 and do not rerun DD-260.
- Accepted numerical endpoints: `81 / 120`; last time: `20.25 s`.
- Worst residual: `1.716812e-12`; all ranks: `258`; worst condition: `1.136251e7`.
- All completed roots succeeded and all completed endpoints were physical.
- Provider calls before the abort: `665520`.
- Failure: Windows denied replacement of the recovery JSON after the complete endpoint-81 temporary file had been written and validated.
- Scientific failure: `False`.
- DD-260 retry: `False`.

The valid endpoint-81 temporary recovery was preserved byte-for-byte as
`logs/dd260_core_v3_c3c4_vapor_holdup_aborted_endpoint81_20260820.json` with
SHA-256 `ca5322f58f6a9ee5944dd98fbc1428bce4afa88c8d82122d6672b2f9674a99ea`.
A separately frozen successor may resume from that state. It must use immutable
per-endpoint journals so status inspection cannot contend with replacement of a
single live recovery file.
