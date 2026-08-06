# DD-152 Zero-Call Multiminute Timing Audit Result

- Classification: `jacobian_dominated`
- Decision: `authorize_separately_frozen_persistent_pool_state_efficiency_probe`
- Analysis wall: `1.118 s`
- Model/provider calls: `0`
- Integrity gates: all passed

## Decomposition

| Metric | DD-150 | DD-151 |
|---|---:|---:|
| Roots | 180 | 900 |
| Jacobian wall | 40.528 s | 380.168 s |
| Non-Jacobian trajectory wall | 7.250 s | 60.215 s |
| Outside-trajectory wall | 18.818 s | 35.967 s |
| Total wall | 66.596 s | 476.349 s |
| Jacobian wall/root | 0.2252 s | 0.4224 s |
| Non-Jacobian wall/root | 0.0403 s | 0.0669 s |

Against exact five-times scaling from DD-150, DD-151 incurred `143.370 s` excess total wall. Positive excess attribution is `88.1%` Jacobian construction and `11.9%` main-process non-Jacobian work. The single pool startup partly offsets the excess.

## Timing Trend

- Coarse Jacobian windows rise from `0.3171` to `0.3638 s/root` (`1.147x`); this does not cross the frozen `1.25x` history threshold.
- Refined Jacobian windows rise from `0.3893` to `0.5344 s/root` (`1.373x`) with root-order correlation `0.953`; this passes the history-dependence gate.
- Solver iterations and residual-evaluation structure do not explain the increase.

The timing is therefore consistent with persistent provider or backend state accumulating over worker lifetime. `ThermoProviderV1` uses exact-state density and heat-capacity caches capped at 2,000 entries and clears each cache wholesale after overflow. That policy is a concrete candidate, but the saved evidence does not prove it is causal.

## Recommendation

Run one separately frozen saved-state Jacobian probe comparing a continuously persistent pool against precommitted fresh-pool boundaries. Require identical matrices and fixed work counts. Do not change cache policy or rerun a trajectory until that probe distinguishes worker lifetime from physical-state cost.
