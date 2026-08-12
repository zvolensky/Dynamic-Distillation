# DD-179 Duration-Scaled Response Adjudication Result

## Verdict

**DD-179 passes every frozen zero-call gate.** DD-178 remains formally failed,
but its immutable ten-second trajectory evidence satisfies the prospective
duration-scaled response policy. One separately frozen longer open-loop
trajectory contract is authorized.

## Evidence

| Metric | Coarse | Refined | Limit |
|---|---:|---:|---:|
| Actual accumulation, lbmol | `0.019841594414340` | `0.019841594413359` | positive |
| Integrated expected, lbmol | `0.019841594413002` | `0.019841594413002` | reference |
| Absolute error, lbmol | `1.3382e-12` | `3.5670e-13` | diagnostic |
| Relative error | `6.7445e-11` | `1.7977e-11` | `<1e-6` |
| Component identity, lbmol | `8.2059e-13` | `2.3346e-13` | `<1e-6` |

The coarse/refined actual accumulation difference is `9.8155e-13 lbmol`,
against `<1e-9 lbmol`. Both saved paths are positive and monotone, and every
non-response DD-178 campaign gate remains passing.

## Policy Decision

Future trajectory response gates shall compare actual accumulation with
integrated expected external flow over the contract's duration. A fixed
absolute maximum copied from a shorter experiment shall not govern a longer
trajectory.

This correction does not reclassify DD-178, change an endpoint, or authorize
a retry. It recognizes the complete saved scientific evidence under a rule
frozen before this adjudication.

## Execution Integrity

- model calls: `0`;
- provider calls: `0`;
- solver calls: `0`;
- endpoint regeneration: `False`;
- wall time: `0.0792 s`;
- DD-178 formal failure preserved: `True`.

## Next Boundary

One separately frozen longer open-loop trajectory may be drafted under both
the DD-176 physical-refinement policy and the DD-179 duration-scaled response
policy. Controllers remain unauthorized.

## Artifacts

- `logs/dd179_core_v3_seven_volume_modest_response_adjudication_contract_20260812.json`
- `logs/dd179_core_v3_seven_volume_modest_response_adjudication_20260812.json`
- `logs/dd179_core_v3_seven_volume_modest_response_adjudication_20260812.md`
- `tools/adjudicate_core_v3_seven_volume_modest_response.py`
