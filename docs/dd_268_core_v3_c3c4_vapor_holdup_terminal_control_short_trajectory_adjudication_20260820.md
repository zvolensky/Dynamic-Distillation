# DD-268 Controlled Refinement Adjudication

- Classification: `controlled_refinement_adjudication_passed`
- Decision: `accept_dd267_scientifically_and_authorize_longer_controlled_trajectory_contract`
- DD-267 classification preserved: `vapor_holdup_terminal_control_short_trajectory_failed`
- DD-267 failed gates: `['refinement']`
- Actual signed path difference: `-2.825821e-05 lbmol`
- Boundary-predicted signed difference: `-2.825821e-05 lbmol`
- Unexplained component maximum: `6.634101e-14 lbmol`
- Provider calls preserved: `27600`
- Wall clock preserved: `7.713 s`
- New DWSIM calls, solve, or state advance: `False`

Nominal and refined backward-Euler paths use slightly different controller outputs. Their inventory difference is therefore expected to equal the difference in integrated external D/B flows, not zero as in the earlier fixed-boundary open-loop gate.
