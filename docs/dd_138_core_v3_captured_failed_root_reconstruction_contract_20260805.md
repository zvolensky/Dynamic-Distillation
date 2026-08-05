# DD-138 Frozen Captured Failed-Root Reconstruction Contract

- Payload SHA-256: `f0d1e01ead23cb659f80b27d2a2cbf8f3d06c59aafa4d1b975b53de20c8653a6`
- Roots: isolated DD-134 coarse `t=7 s` and refined `t=3 s` reconstructions
- Solver: DD-137 captured modified Newton
- Jacobian: exactly one frozen `1e-5`, 21-color matrix per root
- Captured evidence: complete immutable residual/Jacobian/correction/trial vectors and final identity metrics
- Fresh Jacobian, retry, fallback, clipping, projection, state acceptance, timestep, and trajectory: prohibited
- Provider-call limit: `<5000`
- Wall-clock limit: `<180 s`

These are isolated root reconstructions only. No result may become a simulation state.
