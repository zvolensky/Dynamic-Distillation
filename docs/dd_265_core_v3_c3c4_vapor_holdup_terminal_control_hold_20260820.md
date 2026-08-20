# DD-265 Vapor-Holdup Terminal-Control Hold

- Classification: `vapor_holdup_terminal_control_hold_failed`
- Decision: `stop_and_correct_first_controlled_endpoint`
- Evaluated endpoint: `0.25 s`
- Residual maximum: `4.220187e-10`
- Controller residual maximum: `1.340594e-14`
- Drum level, initial to endpoint: `0.440778660` to `0.440778663`
- Sump level, initial to endpoint: `0.523315209` to `0.523315121`
- Distillate, initial to endpoint: `2519.763702` to `2519.608268 lbmol/h`
- Bottoms, initial to endpoint: `4623.210298` to `4625.003902 lbmol/h`
- Maximum temperature movement: `1.449757e-06 F`
- Maximum pressure movement: `2.905915e-06 psia`
- Component identity error: `3.434270e-11 lbmol`
- Energy identity error: `1.938096e-06`
- Jacobian rank: `262 / 262`
- Jacobian condition: `1.142254e+07 / 1.142254e+07`
- DWSIM calls: `71640`
- Wall clock: `19.197 s`
- Serialization recovery execution: `True`
- Alternate numerical setting or trajectory: `False`

The first controlled endpoint is intentionally not motionless. The drum is below setpoint, so distillate begins to decrease and drum level begins to rise. The sump is above setpoint, so bottoms begins to increase and sump level begins to fall. All changes must remain small and smooth.
