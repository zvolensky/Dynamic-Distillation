# DD-092 Frozen Core V3 Numerical-Audit Contract

- Schema: `dd092-core-v3-provider-governed-numerical-contract-v1`
- Payload SHA-256: `ca4f8728bda6b3981d7a1dca9e8a42eee096cf7ed88356852a0d139e8a05311b`
- Preparation base commit: `c18fc05868e3adef5dc8316bfbf2886a3fee9442`
- Workbook SHA-256: `d1442928feb89bded76737614c0751e62bd4383a900b3c56bc243178080ca904`
- Property package: `pr`
- Coordinates/residuals: `40 / 40`
- Full live column residual evaluated during preparation: `False`
- Full nonlinear root solve attempted: `False`
- Dynamic integration attempted: `False`

## Frozen States

- Canonical vector length: `40`
- Perturbed vector length: `40`
- Both drum states were constructed by local direct-fugacity bubble solves.
- Each state carries its independently reconstructed negative condenser duty.

## Execution

After this contract and implementation are committed, execute one two-state audit. Use uncolored central differences at `1e-5` and `5e-6`, then run TP-flash diagnostics and independent PR validation outside the residual/Jacobian path.

No full-column nonlinear solve, root import, mass-matrix work, or dynamic integration is authorized.
