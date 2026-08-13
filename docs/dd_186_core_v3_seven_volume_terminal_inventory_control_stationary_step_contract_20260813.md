# DD-186 Seven-Volume Controlled Stationary-Step Contract

- Payload SHA-256: `a4818febbe5bdb0646eb0923c3610bf1e7ae04e791206cb18c7cba344d624f53`
- Preparation base commit: `6660b0bee09f2c53cc3691c0a38b8da54e34289d`
- Solver: `least_squares(method=trf)`
- Jacobian: topology-generated graph coloring, central difference
- Comparison: one `1.0 s` step versus two `0.5 s` steps
- Terminal setpoints: exact DD-185 live levels
- Initial controller memories and product log ratios: zero
- Product reference rates: fixed DD-169 accepted rates
- Property evaluation during preparation: `False`
- Timestep execution during preparation: `False`

Commit this immutable contract before its one live execution. No disturbance, controller tuning, retry, or trajectory is authorized.
