# DD-209 30-Second Production BDF2 Result

- Classification: `controlled_bdf2_30s_production_passed`
- Decision: `authorize_one_frozen_60s_production_bdf2_contract`
- Completed roots: `360` / `360`
- Coarse/refined stop reasons: `None` / `None`
- Worst residual / condition: `8.375332e-12` / `3.172800e+07`
- Worst shared inventory max / L1: `5.061785e-06` / `1.803948e-05 lbmol`
- Matrix count / logical provider calls: `1362` / `1640840`
- Trajectory / governed wall: `219.115` / `250.435 s`
- Retry, tuning, alternate grid, or fallback: `False`

## Gate Evidence

- Coarse path: `120 x 0.25 s`, complete
- Refined path: `240 x 0.125 s`, complete
- Root, physical, equilibrium, conservation, controller, and response gates: pass
- Shared-time physical/controller/product/level refinement gates: pass at all `120` times
- Coarse/refined total inventory change: `0.0586497688` / `0.0586501094 lbmol`
- Every matrix used all four workers; all `360` roots rebuilt exactly four worker bases
- DWSIM provider ownership: pass; fallback attempted: `False`
- Main-process provider calls: `66,096`
- Exact memoization hits/misses: `16,989` / `49,107`
- Worker plus main-process logical provider calls: `1,640,840`
- Adjusted worker startup: `1.847 s`
- Two-path simulated-time / trajectory-wall ratio: `0.274`

## Interpretation

The controlled seven-volume Core V3 model remains numerically and physically
coherent through 30 simulated seconds on both frozen BDF2 grids. Extending the
horizon from 10 to 30 seconds did not amplify the shared-grid error: the worst
maximum and L1 inventory differences remain `0.189315` and `0.149508` of the
historical DD-190 backward-Euler values. This is evidence of stable integration
over the tested interval, not proof of long-horizon settling or production
economics.

The principal unresolved issue is cost. The accepted production backend makes
the campaign feasible, but two 30-second trajectories still consume more than
four minutes of governed wall time and about 1.64 million logical property
calls. DD-209 therefore authorizes exactly one separately frozen 60-second
coarse/refined validation. It does not authorize unrestricted duration,
controller tuning, timestep changes, or a production-scale dynamic campaign.
