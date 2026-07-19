# DD-089 DWSIM PR Interface-Consistency Contract

- Schema: `dd089-dwsim-pr-phase-interface-consistency-contract-v1`
- Payload SHA-256: `067e0f6e35161a4d935cc60da0986a5933a83ed6f2e6fa7d8f4eaf2cce5db809`
- Preparation base commit: `41fb1623d1ddf97aa64e8c259fecf067c6510657`
- DD-088 result SHA-256: `c9b28e4e2d4d7a1587faa248cdf40dfe2f175c076e2fcaff5501dbc2259c9821`
- DD-088 contract SHA-256: `095011df3c3781eaef660c9b52d8b2209cd8da6a115a4ec2b5d9ab8d3833dd45`
- Samples per fresh process: `16`
- Fresh processes: `3`

## Preserved State

- Temperature: `133.713293493 F`
- Pressure: `218.44 psia`
- Liquid composition: `[0.7030012030418336, 0.2836055267843538, 0.013393270173812703]`
- Direct bubble vapor: `[0.851276948235418, 0.14519622244218763, 0.0035268293223943673]`
- Frozen DD-088 metric: `1.467021e-05`

## Scope

The execution evaluates imposed-phase fugacity, raw TP-flash compositions/K-values, lever-rule closure, fresh-process repeatability, a predefined local T/P/composition neighborhood, and an independent Peng-Robinson fugacity implementation.

No column residual, nonlinear column solve, checkpoint repair, tolerance revision, or dynamic integration is authorized.
