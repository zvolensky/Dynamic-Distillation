# DD-187 Seven-Volume Controlled Moving-Step Contract

- Payload SHA-256: `9e1f098f9c959bd414066b0787942dd1ddc58e5a3ddd5e6496360962ee913cf7`
- Preparation base commit: `f0cb2551967db8dd35712b85a5f3c05ae5dfba05`
- Feed and feed-enthalpy multiplier: `1.001`
- Feed composition and specific enthalpy: unchanged
- Comparison: one `0.25 s` step versus two `0.125 s` steps
- Terminal setpoints and PI tuning: unchanged from DD-186
- Product references: fixed DD-169 rates for every step
- Inventory refinement: frozen physical-scale Core V3 policy
- Property evaluation during preparation: `False`
- Timestep execution during preparation: `False`

Commit before the one live execution. No tuning, retry, alternate disturbance, or trajectory is authorized.
