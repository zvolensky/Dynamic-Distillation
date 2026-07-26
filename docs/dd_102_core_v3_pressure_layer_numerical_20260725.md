# DD-102 Core V3 Pressure-Layer Numerical Result

- Classification: `dd102_core_v3_pressure_layer_numerical_passed`
- Decision: `authorize_one_frozen_pressure_layer_steady_root_contract`
- Wall clock: `8.950 s`
- Provider calls: `9465`
- Worst condition: `1.627829e+02`
- Worst spectrum change: `3.504952e-07`

## State results

### accepted_root_profile

- Pressure, psia: `[218.44, 222.377, 226.896, 229.478, 232.06]`
- Pressure residual, psi: `[1.36618222815493, 2.5129169671956553, 4.4439095563286495, 3.8859639525697527]`
- Liquid-head drop, psi: `[1.1949003988041849, 0.04913737743394172, 0.04964928632546976, 0.02480089084030739]`
- Dry-tray drop, psi: `[0.020917373040878814, 0.019945655370424916, 0.025441157345857508, 0.02623515658995191]`
- Vapor Z: `[0.7395633158070655, 0.7470791570211248, 0.7523982593804628, 0.7579026971704999]`
- Jacobian ranks: `[42, 42]`

### bounded_ordered_pressure_perturbation

- Pressure, psia: `[218.44, 222.39700000000002, 226.93599999999998, 229.538, 232.14000000000001]`
- Pressure residual, psi: `[1.3861928957208425, 2.532924555267466, 4.463915981271252, 3.905967294865626]`
- Liquid-head drop, psi: `[1.1949002514457272, 0.04913727959356639, 0.04964923454235891, 0.024800866926321545]`
- Dry-tray drop, psi: `[0.0209068528334342, 0.019938165138999486, 0.025434784186348185, 0.026231838208074475]`
- Vapor Z: `[0.7394461866582118, 0.746993865090216, 0.7523423879257553, 0.7578749881810988]`
- Jacobian ranks: `[42, 42]`

## Assessment

DD-102 passes every frozen gate. All four numerical Jacobians are rank `42`,
the worst condition is only `162.783`, the worst finite-difference spectrum
change is `3.505e-7`, and no zero or off-registry coupling appears. Component
and energy conservation remain at roundoff. All `9,465` audited DWSIM requests
use direct declared fugacity, enthalpy, liquid density, vapor compressibility,
or preparation-only molecular weight, with no fallback. Runtime is `8.950 s`.

The accepted fixed-pressure root is not a pressure-layer root. Its prescribed
link drops are `[2.582, 2.582, 4.519, 3.937] psi`, while the current hydraulic
relation predicts liquid-plus-dry drops of approximately
`[1.216, 0.0691, 0.0751, 0.0510] psi`. The resulting pressure residuals reach
`4.444 psi`. This discrepancy is expected to move the lower pressure profile
substantially when pressure is solved simultaneously; the old thermodynamic
state must not be assumed to remain a root.

The reduced source workbook has no independent reboiler/sump pressure-drop
geometry. DD-102 therefore uses the selected bottom source stage's declared
tray area and weir geometry for the bottom vapor link, exactly as frozen in the
contract. Before the authorized nonlinear campaign is executed, its separate
contract must either affirm that ownership as the reduced-model definition or
stop and define a physically justified bottom-boundary geometry. This is a
contract decision, not a post-result tuning option.

## Decision

Authorize one separately frozen pressure-layer steady-root contract. Pressure
dynamics, vapor holdup, controllers, and dynamic integration remain
unauthorized.
