# DD-159 Memoized Captured 60-Second Trajectory Result

- Classification: `memoized_captured_longer_trajectory_equivalent`
- Decision: `authorize_separately_frozen_five_minute_memoized_trajectory`
- Completed coarse/refined roots: `60` / `120`
- Memo hits/misses: `147240` / `64440` (`69.5578%` hits)
- Minimum per-root hit fraction: `69.5578%`
- Trajectory wall: `31.636049 s`
- DD-150 trajectory ratio: `0.662147`
- Total wall: `51.546771 s`
- Capture differences: `{'dd134:coarse': 0.0, 'dd134:refined': 0.0}`
- Trajectory differences: `{'coarse': 0.0, 'refined': 0.0}`
- Gates: `{'inherited_dd150_scientific_and_equivalence_gates': True, 'exact_memo_root_and_call_accounting': True, 'memo_hit_fraction_each_root': True, 'trajectory_wall_improvement': True, 'total_wall': True, 'no_rebuild_retry_fallback_or_grid_change': True}`

The only scientific-path change is one exact memo epoch per colored Jacobian. The complete 60-second trajectory is compared against DD-150.
