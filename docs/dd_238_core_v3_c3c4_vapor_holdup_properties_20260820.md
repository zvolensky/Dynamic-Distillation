# DD-238 C3/C4 Vapor-Holdup Live Properties

- Classification: `c3c4_vapor_holdup_property_reconstruction_passed`
- Decision: `authorize_two_phase_vapor_holdup_residual_implementation`
- Physical volumes: `20`
- Audited property calls: `80`
- Total liquid inventory: `2909.337841 lbmol`
- Reconstructed vapor inventory: `473.563386 lbmol`
- Vapor/liquid mole ratio: `1.627736e-01`
- Minimum free vapor volume: `252.365940 ft3`
- Minimum vapor Z: `0.724027`
- Maximum relative EOS residual: `1.123e-16`

DWSIM supplied vapor compressibility and liquid/vapor enthalpy. The accepted aligned-PR route supplied liquid density. No fallback was allowed.

This audit reconstructed resident vapor component inventories and included both liquid and vapor stored energy. It did not evaluate the full successor residual, solve an equation system, take a timestep, or run a trajectory.
