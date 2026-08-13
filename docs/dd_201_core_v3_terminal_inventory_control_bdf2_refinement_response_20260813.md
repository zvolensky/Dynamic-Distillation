# DD-201 BDF2 Response Adjudication Result

- Classification: `bdf2_response_policy_passed`
- Decision: `authorize_one_frozen_modest_bdf2_trajectory_contract`
- Shared times: `8`
- Worst unexplained difference: `1.364242e-12 lbmol`
- Worst response-relative difference: `4.994035e-07`
- DD-200 remains formally failed: `True`
- Model/provider/solver/endpoint-regeneration calls: `0 / 0 / 0 / 0`

## Assessment

Every gate passes. At all eight shared times, the coarse/refined total
inventory difference is reproduced by the independently reconstructed
BE-startup/BDF2 external-flow recurrence. Worst unexplained difference is
`1.364242e-12 lbmol`, far below `1e-10 lbmol`; worst grid difference is
`4.994035e-7` of response, far below `1e-5`.

All DD-200 root, physical, accuracy, response, provider, call, and wall gates
other than the retired absolute signed-total subgate remain passing. DD-200 is
not rerun or reclassified and remains formally failed.

The combined DD-200/DD-201 evidence establishes that controlled BDF2 is
physically coherent over two seconds and reduces worst maximum/L1 inventory
grid error to about `32.5%` of backward Euler on the same grids. One separately
frozen modest BDF2 trajectory contract is authorized. Its duration, grids,
startup policy, solver, accuracy limits, provider work, and wall ceiling must be
fixed before execution; controller tuning remains prohibited.
