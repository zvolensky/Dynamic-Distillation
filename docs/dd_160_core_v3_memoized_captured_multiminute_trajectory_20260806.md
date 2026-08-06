# DD-160 Memoized Captured Five-Minute Trajectory Result

- Classification: `memoized_captured_five_minute_trajectory_passed`
- Decision: `five_minute_memoized_controlled_trajectory_established`
- Completed coarse/refined roots: `300` / `600`
- Complete DD-151 replay: `{'trajectory_differences': {'coarse': 0.0, 'refined': 0.0}, 'trajectory_metadata_equal': {'coarse': True, 'refined': True}, 'capture_differences': {'dd134:coarse': 0.0, 'dd134:refined': 0.0}, 'capture_metadata_equal': {'dd134:coarse': True, 'dd134:refined': True}, 'all_equal': True}`
- Memo hits/misses: `736200` / `322200` (`69.5578%` hits)
- Minimum per-root hit fraction: `69.5578%`
- Trajectory wall: `263.645230 s` (`0.598673x` DD-151)
- Governed total wall: `292.399280 s` (`0.613834x` DD-151)
- Endpoint refinement: `{'inventory': 1.621834509914248e-06, 'energy': 1.602904692434366e-06, 'memory': 1.0454337595888763e-06, 'coordinates': 5.717828751999887e-06, 'product': 5.7164154925351096e-06, 'level': 8.454078137543064e-07}`
- Gates: `{'inherited_dd151_scientific_and_execution_gates': True, 'complete_dd151_replay_exact': True, 'compact_success_evidence': True, 'exact_memo_root_and_call_accounting': True, 'memo_hit_fraction_each_root': True, 'trajectory_wall_improvement': True, 'total_wall': True, 'no_rebuild_retry_fallback_or_grid_change': True}`

The only runtime-path change from DD-151 is exact thermo memoization. All 900 accepted states and full capture digests are compared against DD-151.
