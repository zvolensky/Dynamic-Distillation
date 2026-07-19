# DD-087 Frozen Numerical-Audit Contract

- Schema: `dd087-core-v2-condenser-saturated-liquid-numerical-contract-v1`
- Payload SHA-256: `b7279b3d06f1817e1c15ead66a68450f4dab7cbd4e44ee9c3bc98a83de7776c8`
- Preparation base commit: `6a09334f168bed02a2c0eeb129d7d3b14b9a78b3`
- Workbook SHA-256: `d1442928feb89bded76737614c0751e62bd4383a900b3c56bc243178080ca904`
- Property package: `pr`
- Direct provider bubble API: `False`
- Bubble seed method: local frozen `3 x 3` fugacity solve
- Full residual evaluated during preparation: `False`
- Full nonlinear root solve attempted: `False`
- Dynamic integration attempted: `False`

## Canonical Boundary

- Bubble temperature: `117.816384892 F`
- Bubble residual inf norm: `2.553513e-15`
- Incipient vapor: `[0.9586891509551994, 0.04130955157691584, 1.2974678846972106e-06]`
- Reference condenser duty: `-55003568.3094 BTU/h`
- Signed affine duty scale: `55003568.3094 BTU/h`

## Frozen Audit

Exactly two committed 40-coordinate states are evaluated. Each uses uncolored central differences at `1e-5` and `5e-6`. The exact vectors, scales, row names, tolerances, and local bubble settings are stored in the adjacent JSON contract.

Execution is authorized only after this contract and its implementation are committed. No root solve or integration is authorized.
