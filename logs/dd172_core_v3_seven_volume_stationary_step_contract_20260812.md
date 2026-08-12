# DD-172 Seven-Volume Stationary Implicit-Step Contract

- Payload SHA-256: `1b7851ea5ae6cf10c82135a5b8f6b9bb52a02392cbaec1f12da72b8a62e1dd8e`
- Preparation base commit: `fc7a9135245cf53233406f05cccdd91f429a6da3`
- Solver: `least_squares(method=trf)`
- Jacobian: topology-generated graph coloring, central difference
- Comparison: one `1.0 s` step versus two `0.5 s` steps
- Property evaluation during preparation: `False`
- Timestep execution during preparation: `False`

Commit this immutable contract before its one live execution. No disturbance, controller, retry, or trajectory is authorized.
