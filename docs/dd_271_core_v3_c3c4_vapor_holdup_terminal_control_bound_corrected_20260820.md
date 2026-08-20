# DD-271 Bound-Corrected Controlled Trajectory Result

- Classification: `vapor_holdup_terminal_control_bound_corrected_passed`
- Decision: `authorize_separately_frozen_extended_controlled_trajectory_contract`
- Nominal endpoints: `120` through `30.0 s`
- New/refined roots: `94 / 2`
- Final drum/sump levels: `[0.4407807613063936, 0.5227469832797802]`
- Final D/B: `2501.182520 / 4820.038284 lbmol/h`
- Component identity, nominal/refined: `3.519052e-11 / 3.550160e-11 lbmol`
- Controller-aware refinement error: `3.110845e-13 lbmol`
- Provider calls: `514920`
- Wall clock: `136.129 s`
- Gates: `{'source_replay_parity': True, 'new_endpoints': True, 'nominal_complete': True, 'refinement_complete': True, 'drum_level_monotonic_toward_setpoint': True, 'sump_level_monotonic_toward_setpoint': True, 'distillate_monotonic': True, 'bottoms_monotonic': True, 'component_identity_nominal': True, 'component_identity_refined': True, 'energy_identity_nominal': True, 'energy_identity_refined': True, 'continuity': True, 'controller_aware_refinement_identity': True, 'refinement': True, 'provider': True, 'calls': True, 'wall': True, 'product_outputs_within_contract_bounds': True, 'one_fresh_jacobian_per_new_root': True, 'journals_complete': True, 'no_retry_or_alternate': True}`
- Retry, alternate grid, tuning change, parallel worker, or extension: `False`
