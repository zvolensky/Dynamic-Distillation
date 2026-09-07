# DD-082 Core V2 Five-Volume Steady-Root Campaign

- Classification: `dd082_five_volume_steady_root_failed`
- Decision: `stop_gate_c_and_retire_this_operating_specification`
- Campaign accepted: `False`
- Maximum root disagreement: `2.1211237373398255e-09`
- Total wall clock: `31.847 s`
- Solver: `scipy.optimize.least_squares`, `method=trf`
- Five-volume continuation/fallback attempted: `False`

## Attempts

| Start | Solver success | Residual inf | Rank | Condition | Active bounds | Accepted |
|---|---|---:|---:|---:|---:|---|
| canonical_mini8_derived | True | 0.009159988953902269 | 38 | 19219.17645482136 | 1 | False |
| bounded_deterministic_perturbation | True | 0.009159988953666659 | 38 | 19219.175757743673 | 1 | False |
| independent_smooth_profile | True | 0.009159988934201172 | 38 | 19219.175741334406 | 1 | False |

## Pairwise Root Agreement

- canonical_mini8_derived vs bounded_deterministic_perturbation: `2.5984564547709586e-11`
- canonical_mini8_derived vs independent_smooth_profile: `2.1211237373398255e-09`
- bounded_deterministic_perturbation vs independent_smooth_profile: `2.0951391728465573e-09`

## Reconciliation

- Dominant movement family: `vapor_composition`
- Interpretation: Movement classification uses the largest transformed-coordinate RMS across the three fixed starts. It is a diagnostic, not a weighted solver objective.

## DD-058 Qualitative Reference

DD-058 remains a controlled v1 operational checkpoint, not equation truth for v2. DD-082 uses no DD-058 value in its residual, bounds, scales, seed construction, or acceptance.

## Decision

DD-082 fails the Gate C hard stop. Do not add DD-083 solver tuning, continuation, geometry changes, or another operating-specification variant. The prescribed-pressure, prescribed-vapor five-volume case has not demonstrated a common physical steady root.
