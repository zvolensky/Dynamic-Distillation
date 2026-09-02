# Core V3 water-methanol stationary Jacobian

- Result: `stationary_jacobian_passed`
- Next gate: `authorize_one_bounded_stationary_solve`
- Size and color groups: `100 / 22`
- Liquid-density provider: `clapeyron_vtpr`
- Rank at both step sizes: `100 / 100`
- Condition number: `5.078713e+03 / 5.078713e+03`
- Matrix change between step sizes: `1.261252e-10`
- Singular-value change: `5.165636e-11`
- Direct column checks passed: `12/12`
- Live property calls: `6720`
- Wall time: `1.490 seconds`
- Nonlinear solve or timestep: `False`

The Jacobian is full rank, well within the conditioning limit, and stable when the numerical step is halved.
