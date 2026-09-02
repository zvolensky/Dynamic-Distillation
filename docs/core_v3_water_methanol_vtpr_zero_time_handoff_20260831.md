# Core V3 water-methanol zero-time dynamic handoff

- Result: `fixed_product_zero_time_dynamic_handoff_passed`
- Decision: `authorize_separately_bounded_fixed_product_hold_step`
- Handoff mode: `fixed_terminal_products`
- Residual maximum: `1.199041e-14`
- Physical inventory-rate maximum: `0.000000e+00 lbmol/h`
- Maximum stationary/dynamic state difference: `0.000000e+00`
- Reflux-drum/bottom-sump levels: `0.504876 / 0.580611`
- Fixed D/B: `6732.991788 / 9140.288212 lbmol/h`
- Instantaneous product-flow jump: `False`
- Jacobian rank: `98 / 98`
- Jacobian condition: `1.663269e+06 / 1.663269e+06`
- Matrix step change: `7.202700e-11`
- Missing controller specifications: `['Top Level SP Frac', 'Top Level Kc', 'Bottom Level SP Frac', 'Bottom Level Kc', 'Bottom Level Ti (sec)']`
- Nonlinear solve or accepted timestep: `False`

The stationary state is mapped without a jump into the generic fixed-product dynamic DAE. No controller settings were invented for the workbook.
