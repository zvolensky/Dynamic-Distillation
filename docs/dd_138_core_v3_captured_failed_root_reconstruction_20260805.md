# DD-138 Captured Failed-Root Reconstruction Result

- Classification: `audit_invalid`
- Decision: `stop_pending_capture_integrity_review`
- coarse success/residual: `False` / `5.091893162e-08`
- coarse iterations/trials: `2` / `5`
- coarse rank/condition: `50` / `2.084335314e+05`
- coarse final vs DD-135 stalled coordinate: `8.876875391e-09`
- coarse residual/coordinate identity: `0.0e+00` / `3.9e-09`
- refined success/residual: `True` / `1.686514169e-10`
- refined iterations/trials: `2` / `2`
- refined rank/condition: `50` / `7.286666781e+05`
- refined final vs DD-135 stalled coordinate: `3.257507254e-08`
- refined residual/coordinate identity: `0.0e+00` / `1.9e-09`
- DWSIM calls: `2605`
- Wall clock: `3.105 s`

No reconstructed endpoint was accepted as a simulation state; no timestep or trajectory advanced.

## Formal Result

DD-138 is formally invalid because the frozen solver-coordinate versus evaluation-coordinate identity gate required exact equality. The live backward-Euler kernel intentionally replaces each nominal component-rate coordinate with the actual finite-step rate implied by its exponential positive-inventory map. The maximum expected representation differences are `3.922609e-9` for the coarse root and `1.946317e-9` for the refined root. Residual identity remains exactly zero for both roots.

## Scientific Evidence

The coarse reconstruction reproduces a complete two-iteration frozen-Jacobian line-search failure. Its final residual is `5.091893162e-8`, only `7.111469e-13` from DD-134's saved scalar, and all four second-iteration fractions are rejected. The refined reconstruction instead converges in two full corrections to `1.686514169e-10` with no rejection. Both matrices remain rank `50/50`; their conditions are `2.084335e5` and `7.286667e5`.

This evidence is not yet accepted because the coordinate-identity gate failed. No adaptive solver or trajectory is authorized. A static, zero-provider adjudication may replace only that coordinate gate by analytically verifying the documented exponential nominal-to-actual rate map while preserving every other DD-138 gate and both root outcomes.
