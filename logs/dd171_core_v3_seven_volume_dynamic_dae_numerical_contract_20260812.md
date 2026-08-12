# DD-171 Seven-Volume Dynamic DAE Numerical Contract

- Contract payload SHA-256: `f1dbdc61d411da0c198f72a3792ee2c9f88410ad1e8396752ad8981bf417cf1a`
- Preparation base commit: `33c631dcba4cd8c1f56007dbcf038dbff7f3c889`
- Leading system: `54 x 54`
- Storage-gradient steps: `1e-5`, `5e-6`
- Leading-Jacobian steps: `1e-5`, `5e-6`
- Exact-state provider memoization: enabled
- Property calls during preparation: `False`
- Nonlinear solve or timestep during preparation: `False`

## Authorization

Commit this contract before its one live execution. The execution may evaluate the accepted root, storage derivatives, and two leading Jacobians only. It may not solve for a state, choose a timestep, run a controller, or integrate dynamics.
