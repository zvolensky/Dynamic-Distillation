# DD-133 DD-132 Physical-Equivalence Adjudication Result

- Classification: `dd133_passed`
- Decision: `authorize_frozen_modified_newton_short_controlled_trajectory_contract`
- Tightest metric: `half2.bottoms_relative_difference` = `6.685187139e-08`
- Tightest limit: `<1.000000000e-07`
- Decoded states physical: `True`
- Stored products match coordinates: `True`
- Live property calls: `0`
- Residual/Jacobian evaluations: `0/0`
- Timesteps or dynamics: `0`

DD-130 and DD-132 retain their original formal classifications. This adjudication only determines whether their saved physical endpoints are equivalent under the frozen DD-133 limits.

## Decision Detail

All `57` endpoint metrics pass across the coarse, half1, and half2 results. The
previously disputed half2 bottom-to-stripping vapor flow differs by
`1.017993196e-7` relative, below the frozen `<2e-7` physical limit. The tightest
normalized gate is instead the half2 bottoms-flow difference at
`6.685187139e-8` against `<1e-7`.

Component inventories, holdups, liquid and vapor compositions, component and
energy rates, temperatures, liquid and vapor flows, pressure, condenser duty,
controller states and rates, levels, and product flows are physically
equivalent. The comparison required no DWSIM or model evaluation. A separately
frozen modified-Newton short controlled-trajectory contract is authorized; no
trajectory has yet been executed.
