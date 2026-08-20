# DD-255 Modified-Newton Vapor-Holdup Trajectory Result

- Classification: `modified_newton_vapor_holdup_trajectory_failed`
- Decision: `retain_full_jacobian_refresh_per_iteration`
- Endpoints completed: `4`
- Maximum endpoint-coordinate difference: `1.184879e-09`
- Jacobian builds by root: `{'dd254:modified_newton:root_1': 1, 'dd254:modified_newton:root_2': 1, 'dd254:modified_newton:root_3': 1, 'dd254:modified_newton:root_4': 1}`
- Provider calls: `34440` versus `174480` baseline
- Call ratio: `0.197387`
- Wall: `12.524064 s` versus `27.168700 s` baseline
- Speedup: `2.169x`
- Gates: `{'path_complete': True, 'scientific_endpoints': True, 'one_fresh_jacobian_per_root': True, 'endpoint_equivalence': False, 'response_equivalence': True, 'component_identity': True, 'energy_identity': True, 'provider': True, 'call_count': True, 'call_reduction': True, 'wall_clock': True, 'wall_reduction': True, 'serial_only': True, 'no_retry_or_controller': True}`
- Retry, alternate grid, parallel worker, controller, or longer trajectory: `False`
