# DD-202 Controlled BDF2 Modest-Trajectory Result

- Classification: `controlled_bdf2_refinement_passed`
- Decision: `authorize_controlled_bdf2_integration_milestone`
- Completed roots: `120`
- Worst residual / condition: `8.375332e-12` / `3.172745e+07`
- Worst shared inventory max / L1: `5.061785e-06` / `1.803948e-05 lbmol`
- DD-190 backward Euler max / L1 ratios: `0.189315` / `0.149508`
- Improvement from DD-190 backward Euler: `81.07%` maximum / `85.05%` L1
- Worst rate / algebraic refinement: `4.011255e-07` / `4.023492e-07`
- Worst PI-memory / product / level refinement: `6.091078e-10` / `1.041090e-08` / `1.225224e-09`
- Coarse/refined accumulation: `1.983019e-02` / `1.983029e-02 lbmol`
- Worst unexplained cross-grid total: `7.275958e-12 lbmol`
- Worst response-relative cross-grid total: `5.203283e-06`
- Provider calls / wall: `542368` / `159.195 s`
- Root/shared-time failures: `0 / 0`
- Retry, tuning, alternate grid, or longer trajectory: `False`

## Decision

The ten-second BDF2 proof passes every frozen gate. All `40 x 0.25 s` and
`80 x 0.125 s` roots retain rank `58`; worst condition is `3.172745e7` and
worst scaled residual is `8.375332e-12`. BDF2 resolves DD-190's specific
backward-Euler timestep-refinement stop with substantially more than the
required `20%` accuracy improvement.

The legacy absolute signed-total diagnostic fails at 34 shared times, but the
accepted DD-189/DD-201 policy explains every difference from independently
integrated external flow. No physical, conservation, response, provider,
accuracy, call, or wall gate fails.

DD-202 authorizes a separately frozen controlled BDF2 integration milestone.
It does not authorize controller tuning, a grid change, fallback behavior, or
an unrestricted production trajectory.
