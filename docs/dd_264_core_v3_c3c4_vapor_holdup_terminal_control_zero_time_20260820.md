# DD-264 Vapor-Holdup Terminal-Control Zero-Time Audit

- Classification: `vapor_holdup_terminal_control_zero_time_passed`
- Decision: `authorize_separately_frozen_stationary_control_hold_step`
- Residual maximum: `3.050319e-11`
- Controller residual maximum: `0.000000e+00`
- Physical inventory-rate maximum: `0.000000e+00 lbmol/h`
- Reflux-drum level: `0.440779`
- Bottom-sump level: `0.523315`
- Level setpoints: `[0.5, 0.5]`
- Initial D/B: `2519.763702 / 4623.210298 lbmol/h`
- Controller memory: `[0.0296106699691161, -0.18652166871547848]`
- Controller rates: `[-0.0002467555830759675, 0.001554347239295654] 1/s`
- Instantaneous product-flow jump: `False`
- Jacobian rank: `262 / 262`
- Jacobian condition: `1.142253e+07 / 1.142253e+07`
- Provider calls: `7880`
- Wall clock: `5.835 s`
- Nonlinear solve or accepted timestep: `False`

The physical column and product rates are motionless at controller activation. The PI memories cancel the initial proportional terms, so enabling control causes no D/B jump. The integrators are not stationary because the live levels differ from the 50% setpoints; they will begin a smooth corrective response on the first timestep.
