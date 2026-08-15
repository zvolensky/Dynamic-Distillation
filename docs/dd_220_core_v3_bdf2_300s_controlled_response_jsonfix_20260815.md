# DD-220 Controlled-Response Adjudication Result

- Classification: `controlled_five_minute_dynamics_accepted`
- Decision: `accept_dd218_science_under_controlled_response_policy`
- Inventory initial / peak / final: `2404.021619110` / `2404.288656299` / `2404.288048638 lbmol`
- Peak time / final decline samples: `280.0 s` / `4`
- Bottoms initial / final: `4922.021660` / `4929.404745 lbmol/h`
- Level range: `0.427453` to `0.459899`
- Model/provider/solver/timestep calls: `0`
- DD-218 formal classification: unchanged

## Interpretation

DD-218's sole formal failure came from a short-horizon smoke-test assumption
that total inventory must increase at every sample. Over five minutes, the
terminal inventory controller begins correcting the initial accumulation: the
inventory peaks at `280 s` and then declines while bottoms withdrawal rises.
The response is bounded, physical, and exactly explained by external flows.

The saved DD-218 science is therefore accepted as a controlled five-minute
dynamic trajectory. This decision applies to the seven-volume Core V3 reduced
column. It does not reclassify the immutable DD-218 campaign record and does
not yet validate the full production-column configuration.
