# DD-173 Seven-Volume Moving-Step Contract

- Payload SHA-256: `382905e40b82ef7eabb38d7e911f4df73115be75ee19cfd8664b586ba6b15a54`
- Preparation base commit: `aaca57c705000d9ab190fe4de099f69bc3d535a1`
- Feed-rate multiplier: `1.001`
- Feed-enthalpy multiplier: `1.001`
- Feed composition and specific enthalpy: unchanged
- Comparison: one `1.0 s` step versus two `0.5 s` steps
- Solver/Jacobian: unchanged from DD-172
- Live property evaluation during preparation: `False`

Commit before the one live execution. No controller, retry, alternate disturbance, or multi-step trajectory is authorized.
