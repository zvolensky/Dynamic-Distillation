# DD-141 ThermoProvider Cache-Resolution Result

- Classification: `rounded_property_cache_alias_confirmed`
- Decision: `authorize_exact_state_property_cache_key_correction`
- Temperature perturbations: `[0.001, 0.0005]` F
- Pressure perturbations: `[0.0001, 5e-05]` psia
- DD-140 inverse-step ratios: coarse `2.000000000`, refined `2.002100063`
- Density cache aliases: temperature, pressure, and composition all confirmed
- Heat-capacity cache alias: `True`
- DWSIM/property, residual, Jacobian, solve, state advance, and timestep calls: `0`

The rounded cache keys merge distinct states and return whichever value was requested first. An exact-state key correction is authorized before any solver work resumes.
