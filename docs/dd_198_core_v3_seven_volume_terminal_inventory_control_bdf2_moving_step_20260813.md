# DD-198 Controlled BDF2 Moving-Step Result

- Classification: `controlled_bdf2_moving_step_passed`
- Decision: `authorize_one_frozen_short_bdf2_refinement_contract`
- Residual: `3.528219e-12`
- Rank / condition: `58 / 3.172741e+07`
- Function/Jacobian evaluations: `4 / 2`
- Maximum BDF2/BE inventory difference: `8.664731e-07 lbmol`
- BDF2 Richardson max error: `1.669391e-06 lbmol`
- BE Richardson max error: `2.535865e-06 lbmol`
- Accuracy improvement ratio: `0.658313`
- Provider calls: `2550`
- Wall clock: `6.252 s`
- Retry, tuning, alternate step, or trajectory: `False`

## Assessment

Every frozen gate passes. The single moving BDF2 root closes at
`3.528219e-12` in four residual and two Jacobian evaluations. The Jacobian
retains rank `58` with condition `3.172741e7`; physicality, equilibrium,
component/energy conservation, controller closure, and every BDF2 kinematic
identity pass. Global component accumulation closes within
`4.786374e-13 lbmol`.

The endpoint remains close to the accepted DD-187 two-half-step
backward-Euler result: maximum component-inventory difference is
`8.664731e-7 lbmol`, L1 difference is `3.094640e-6 lbmol`, and rate/algebraic
coordinate differences are below `7.16e-8`.

The accuracy gate is the important result. Against the frozen first-order
Richardson inventory estimate, BDF2's maximum error is `1.669391e-6 lbmol`
versus `2.535865e-6 lbmol` for refined backward Euler. The ratio is `0.658313`,
so BDF2 reduces that error by about `34.2%` on its first moving endpoint.

The execution uses `2,550` logical DWSIM calls in `6.252 s`. No retry,
alternate timestep, controller tuning, accepted trajectory, or fallback occurs.

## Decision Boundary

One separately frozen short BDF2 grid-refinement contract is authorized. Each
grid must use one accepted backward-Euler startup step followed by constant-step
BDF2, retain the unchanged disturbance/controllers/provider, and compare shared
physical endpoints under the existing response-scaled conservation policy. The
contract must fix duration, grids, solver, performance ceiling, and acceptance
limits before execution. No long trajectory or controller tuning is authorized.
