# DD-173 Seven-Volume Open-Loop Moving-Step Contract

## Purpose

DD-173 is the first authorized nonstationary timestep for the seven-volume
Core V3 model. It tests local physical direction and time refinement without
starting a trajectory.

## Frozen Disturbance

- Multiply every feed component rate by `1.001`.
- Multiply total feed enthalpy by `1.001`.
- Preserve feed composition and specific enthalpy exactly.
- Keep pressure, reflux, reboiler duty, product draws, geometry, and all other
  operating inputs unchanged.

The total feed increment is `7.142974 lbmol/h`, implying an approximately
`0.001984 lbmol` one-second global inventory response before the small product-
composition response is included.

## Frozen Campaign

- One `1.0 s` backward-Euler root
- Two successive `0.5 s` roots
- DD-172 solver, graph coloring, finite-difference step, scales, and exact-state
  memoization unchanged

## Frozen Gates

- Every residual below `1e-8`, rank `54/54`, condition below `1e8`
- Physicality, equilibrium, conservation, and exact discrete kinematics
- Positive and detectable total inventory response between `1e-4` and
  `1e-2 lbmol`
- Global component-inventory identity below `1e-6 lbmol`
- Full/refined relative inventory difference below `1e-7`
- Full/refined rate and algebraic differences below `1e-5`
- Full/refined total-inventory difference below `1e-6 lbmol`
- Fewer than `30,000` logical provider calls and less than `120 s` wall time

## Scope Boundary

No controller, retry, alternate disturbance, or multi-step trajectory is
authorized. A complete pass authorizes only one separately frozen short
open-loop trajectory contract.

## Frozen Artifact

- `logs/dd173_core_v3_seven_volume_moving_step_contract_20260812.json`
- Payload SHA-256:
  `382905e40b82ef7eabb38d7e911f4df73115be75ee19cfd8664b586ba6b15a54`
