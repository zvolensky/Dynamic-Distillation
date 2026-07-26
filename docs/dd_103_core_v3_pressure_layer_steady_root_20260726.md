# DD-103 Core V3 Pressure-Layer Steady-Root Result

- Classification: `dd103_core_v3_pressure_layer_steady_root_failed`
- Decision: `stop_algebraic_pressure_path_before_dynamics`
- Wall clock: `16.835 s`
- Provider calls: `27721`
- Common-root difference: `2.445001e-05`
- Worst condition: `6.595859e+01`

## accepted_algebraic_old_pressure

- Success: `True`
- Evaluations: `24` residual / `14` Jacobian
- Final residual: `8.947348e-03`
- Pressure, psia: `[218.44, 218.49161600355126, 218.56775728346216, 218.63694477824208, 218.65850081106942]`
- Temperature, F: `[133.6542682054026, 152.8276937105928, 170.6281109551002, 180.1459725188992, 194.43053062639638]`
- Vapor flow, lbmol/h: `[7611.8919335811215, 7650.396075693663, 7750.007278755104, 8064.948539878148]`
- Liquid flow, lbmol/h: `[5611.997072199951, 12659.308005416126, 12628.057889318505]`
- Condenser duty, MMBTU/h: `-52.387528`

## source_algebraic_projected_pressure

- Success: `True`
- Evaluations: `20` residual / `12` Jacobian
- Final residual: `8.947908e-03`
- Pressure, psia: `[218.44, 218.49161546570275, 218.56775620382405, 218.63694409757184, 218.65850010798854]`
- Temperature, F: `[133.65394385540873, 152.82592963072895, 170.62935782324917, 180.1460581677476, 194.43056943538673]`
- Vapor flow, lbmol/h: `[7611.887222003223, 7650.468385642412, 7749.8879397707815, 8064.917617429558]`
- Liquid flow, lbmol/h: `[5611.921786394025, 12659.39714578915, 12628.05909327132]`
- Condenser duty, MMBTU/h: `-52.387240`

## Assessment

DD-103 fails its frozen acceptance contract cleanly. Both bounded solves report
successful termination and approach nearly the same physical state, but their
scaled residual infinity norms stop at `8.947348e-3` and `8.947908e-3`, well
above the required `1e-8`. Their scaled-coordinate separation is
`2.445001e-5`, also above the `1e-7` common-root limit.

This is not a rank, conditioning, property-provider, conservation, bound, or
pressure-ordering failure. Both endpoint Jacobians have algebraic column rank
`27/27`, the worst condition is only `65.959`, the finite-difference spectra
are stable, every coordinate remains interior, component and energy
telescoping remain at roundoff, and all `27,721` provider calls pass. The
hydraulic pressure profile itself nearly closes at approximately
`[218.4400, 218.4916, 218.5678, 218.6369, 218.6585] psia`, with maximum link
residual about `2.1e-5 psi`.

The decisive limitation is formulation scope. DD-103 fixes all 15 conserved
inventory coordinates at the DD-094 fixed-pressure root and asks only 27
algebraic coordinates to satisfy all 42 zero-rate equations after pressure
ownership changes. The stable nonzero residual floor shows that this frozen
inventory state cannot be reconciled into an exact pressure-enabled steady
root by algebraic adjustment alone under the declared equations.

## Decision

Retire algebraic-only pressure repair. Do not retry with another pressure
seed, solver option, tolerance, scale, bottom geometry, or liquid-head rule.
The next permitted increment is a property-free structural contract for a
pressure-enabled implicit DAE in which the conserved inventories and their
rates participate simultaneously with the algebraic pressure variables.
Dynamic integration, pressure controllers, vapor holdup, and a numerical
implicit step remain unauthorized until that structural contract passes.
