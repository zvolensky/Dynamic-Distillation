# DD-174 Moving-Step Physical-Scale Adjudication Result

## Verdict

**DD-174 passes every frozen physical-scale gate using only the immutable
DD-173 endpoint arrays.** DD-173 remains formally failed. The result
authorizes one separately frozen smaller-timestep moving proof, not a
trajectory.

## Evidence

| Metric | Result | Limit | Fraction of limit |
|---|---:|---:|---:|
| Maximum absolute component difference | `3.275352e-5 lbmol` | `<1.0e-4 lbmol` | `0.328` |
| Maximum state-relative difference with `1 lbmol` floor | `1.522960e-6` | `<1.0e-5` | `0.152` |
| Maximum volume-holdup-relative difference | `7.203869e-7` | `<1.0e-6` | `0.720` |
| Component-difference L1 | `1.164692e-4 lbmol` | `<2.0e-4 lbmol` | `0.582` |
| Absolute signed total difference | `5.746514e-13 lbmol` | `<1.0e-9 lbmol` | `5.75e-4` |

The maximum absolute and volume-scaled differences occur for n-butane in the
feed volume. The maximum state-relative difference occurs for n-pentane in
the same volume. DD-173's full and refined global inventory responses remain
effectively identical, and its component accumulation identities remain at
machine scale.

## Interpretation

The failed DD-173 relative metric amplified a few micro-moles of local
first-order timestep error by dividing by a small component inventory. On
absolute inventory, local-volume, column-total, conservation, and response
scales, the endpoints are physically close under the limits declared before
this adjudication.

This does not erase DD-173's precommitted failure and does not establish
trajectory convergence. The volume-holdup-relative result uses about `72%`
of its limit, so another one-second attempt would add little evidence. The
next bounded test should retain the exact `+0.1%` feed disturbance and solver
but compare one `0.25 s` backward-Euler step with two successive `0.125 s`
steps. That prospective contract must be frozen separately.

## Execution Integrity

- model calls: `0`;
- provider calls: `0`;
- solver calls: `0`;
- endpoint regeneration: `False`;
- wall time: `0.0871 s`;
- source DD-173 formal failure preserved: `True`.

## Artifacts

- `logs/dd174_core_v3_moving_step_physical_adjudication_contract_20260812.json`
- `logs/dd174_core_v3_moving_step_physical_adjudication_20260812.json`
- `logs/dd174_core_v3_moving_step_physical_adjudication_20260812.md`
- `tools/adjudicate_core_v3_seven_volume_moving_step.py`
