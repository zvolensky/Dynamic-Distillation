# DD-267 Short Controlled Trajectory Result

- Classification: `vapor_holdup_terminal_control_short_trajectory_failed`
- Decision: `stop_controlled_trajectory_extension`
- Nominal endpoints: `4` through `1.0 s`
- Final refinement endpoints: `2`
- Final drum/sump levels: `[0.44077868213183136, 0.5233143384462194]`
- Final D/B: `2519.142041 / 4630.369592 lbmol/h`
- Worst continuity: `{'temperature_F': 5.635208026433247e-06, 'pressure_psia': 8.74439459153109e-06, 'composition': 2.5089577054826506e-08, 'flow_relative': 1.2036548385273162e-05, 'phase_inventory_relative': 6.762012732658883e-07, 'duty_relative': np.float64(6.5249569960954924e-06), 'product_relative': 0.00038795632411157786}`
- Final-step refinement: `{'component_max_lbmol': 2.306069245605613e-05, 'component_l1_lbmol': 3.308161382106073e-05, 'signed_total_lbmol': 2.8258207470648056e-05, 'temperature_F': 3.3171724567182537e-07, 'pressure_psia': 3.52252641278028e-07, 'flow_relative': 4.108988737948438e-07, 'phase_transfer_scaled': 4.425587764453013e-07, 'duty_relative': np.float64(4.4081026706783167e-07), 'level_fraction': 2.115543007441545e-08, 'product_relative': 1.7103906479611864e-07}`
- Provider calls: `27600`
- Wall clock: `7.713 s`
- Gates: `{'source_parity': True, 'new_endpoints': True, 'nominal_complete': True, 'refinement_complete': True, 'drum_level_monotonic_toward_setpoint': True, 'sump_level_monotonic_toward_setpoint': True, 'distillate_monotonic': True, 'bottoms_monotonic': True, 'component_identity_nominal': True, 'component_identity_refined': True, 'energy_identity_nominal': True, 'energy_identity_refined': True, 'continuity': True, 'refinement': False, 'provider': True, 'calls': True, 'wall': True, 'one_fresh_jacobian_per_new_root': True, 'no_retry_or_alternate': True}`
- Retry, alternate grid, tuning change, parallel worker, or extension: `False`
