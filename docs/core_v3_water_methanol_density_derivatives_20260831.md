# Core V3 water-methanol liquid-density derivative audit

- Finding: `liquid_density_derivative_noise_isolated`
- Decision: `repair_or_replace_live_liquid_density_derivative_path_before_resolving`
- Density derivative change range: `4.999824e-01 to 9.999132e-01`
- Largest enthalpy or fugacity derivative change: `3.844278e-09`
- Live property calls: `64`
- Nonlinear solve, retry, or timestep: `False`

## Meaning

The liquid-density derivative changes sharply when the numerical step is halved, while liquid enthalpy and fugacity derivatives remain stable. This isolates the failed stationary solve to the live liquid-density derivative path rather than the UNIFAC equilibrium or enthalpy calculations.
