# DD-262 Thirty-Second Balance Adjudication Result

- Classification: `thirty_second_balance_adjudication_passed`
- Decision: `accept_dd261_scientific_trajectory_through_thirty_seconds`
- Replayed endpoints: `120`
- Component identity: `1.717577e-12 lbmol`
- Energy identity relative: `3.954407e-11`
- Endpoint-81 parity: `0.000000e+00`
- Final-state parity: `0.000000e+00`
- Provider calls: `9600`; wall: `3.017 s`
- Gates: `{'coordinate_count': True, 'endpoint81_parity': True, 'final_state_parity': True, 'component_identity': True, 'energy_identity': True, 'provider': True, 'provider_calls': True, 'wall_clock': True, 'no_solve_or_state_advance': True}`

DD-261's formal failed classification is preserved. DD-262 corrects only the
aggregate assessment: the expected changes are sums of all endpoint boundary
rates, not the final endpoint rate multiplied by the full duration.

Nonlinear solve, timestep, state advance, retry, or controller: `False`
