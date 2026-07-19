# DD-093 Frozen Core V3 Steady-Root Contract

- Schema: `dd093-core-v3-steady-root-contract-v1`
- Payload SHA-256: `f4f121a8d946814c1b6fe8c9be8122a10264a1e5a600061f2b71e1368547a338`
- Preparation base commit: `f53c4b8fc59058259ddf2ee542a2ef067ebf236b`
- DD-092 payload: `ca4f8728bda6b3981d7a1dca9e8a42eee096cf7ed88356852a0d139e8a05311b`
- System: unchanged Core V3 `40 x 40` residual
- Solver: `scipy.optimize.least_squares(method="trf")`
- Starts: three complete 40-coordinate vectors
- Campaign executed during preparation: `False`

## Third Start

The third start is a fully distinct smooth five-volume profile, including a separately selected drum liquid composition, its own direct-fugacity bubble reconstruction, and its own condenser-energy duty reconstruction.

## Authorization

This commit defines the one permitted campaign. It does not execute the nonlinear solve or authorize dynamic work.
