# DD-153 Worker-Lifetime Efficiency Probe Result

- Classification: `persistent_worker_lifetime_slowdown_confirmed`
- Decision: `authorize_separately_frozen_pool_renewal_cadence_benchmark`
- Provider calls: `14112`
- Wall: `155.335 s`
- Gates: all passed

## Checkpoints

| Path/root | Aged pool | Fresh median | Aged/fresh | Repeat spread |
|---|---:|---:|---:|---:|
| Coarse 60 | 0.3359 s | 0.2199 s | 1.527 | 2.79% |
| Coarse 180 | 0.3306 s | 0.2297 s | 1.439 | 11.70% |
| Coarse 300 | 0.3665 s | 0.2339 s | 1.566 | 0.46% |
| Refined 120 | 0.4100 s | 0.2263 s | 1.812 | 6.13% |
| Refined 360 | 0.4785 s | 0.2250 s | 2.126 | 0.29% |
| Refined 600 | 0.5551 s | 0.2224 s | 2.496 | 5.46% |

All six checkpoints exceed the frozen `1.25x` threshold; the median ratio is `1.689x`. Fresh late/early timing is `1.064x` for coarse and `0.983x` for refined, both within the physical-state limit. All 12 fresh matrices reproduce the saved DD-151 matrices bit-for-bit.

## Conclusion

Persistent worker lifetime, rather than increasing physical-state difficulty, causes the dominant Jacobian slowdown. The probe does not yet distinguish `ThermoProviderV1` cache behavior from other DWSIM/.NET process state.

Fresh-pool startup averages `6.814 s`, so recycling every matrix would be counterproductive. The next bounded step is a saved-state cadence benchmark that balances recovered Jacobian speed against renewal overhead. No nonlinear root was solved and no state or trajectory advanced.
