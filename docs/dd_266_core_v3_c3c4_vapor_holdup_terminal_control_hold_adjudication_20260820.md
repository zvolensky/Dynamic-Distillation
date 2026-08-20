# DD-266 Controlled Hold Adjudication

- Classification: `vapor_holdup_terminal_control_hold_adjudication_passed`
- Decision: `accept_dd265_endpoint_scientifically_and_authorize_short_controlled_trajectory_contract`
- DD-265 classification preserved: `vapor_holdup_terminal_control_hold_failed`
- DD-265 failed gates: `['energy_identity', 'solver']`
- Accepted endpoint residual: `4.220187e-10`
- Energy identity absolute error: `1.938096e-06 BTU`
- Residual-consistent energy bound: `7.598056e-04 BTU`
- Energy margin: `392.0x`
- Endpoint D/B: `2519.608268 / 4625.003902 lbmol/h`
- Endpoint levels: `[0.44077866257450454, 0.523315120557669]`
- Jacobian rank: `[262, 262]`
- New DWSIM calls, solve, or state advance: `False`

DD-265 remains formally failed. Its saved endpoint is nevertheless a valid physical root of the frozen controlled step. SciPy exhausted the fixed evaluation budget after the residual target was already met, and the tiny aggregate energy discrepancy lies well inside the error implied by that same residual target.
