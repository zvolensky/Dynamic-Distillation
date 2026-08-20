# DD-269 Five-Second Controlled Trajectory Result

- Classification: `vapor_holdup_terminal_control_five_second_passed`
- Decision: `authorize_separately_frozen_extended_controlled_trajectory_contract`
- Nominal endpoints: `20` through `5.0 s`
- New/refined roots: `16 / 2`
- Final drum/sump levels: `[0.4407789095752894, 0.5232975429921715]`
- Final D/B: `2516.657110 / 4658.612086 lbmol/h`
- Component identity, nominal/refined: `3.430971e-11 / 3.431258e-11 lbmol`
- Controller-aware refinement error: `2.920626e-13 lbmol`
- Provider calls: `101160`
- Wall clock: `29.187 s`
- Gates: `{'source_replay_parity': True, 'new_endpoints': True, 'nominal_complete': True, 'refinement_complete': True, 'drum_level_monotonic_toward_setpoint': True, 'sump_level_monotonic_toward_setpoint': True, 'distillate_monotonic': True, 'bottoms_monotonic': True, 'component_identity_nominal': True, 'component_identity_refined': True, 'energy_identity_nominal': True, 'energy_identity_refined': True, 'continuity': True, 'controller_aware_refinement_identity': True, 'refinement': True, 'provider': True, 'calls': True, 'wall': True, 'one_fresh_jacobian_per_new_root': True, 'journals_complete': True, 'no_retry_or_alternate': True}`
- Retry, alternate grid, tuning change, parallel worker, or extension: `False`
