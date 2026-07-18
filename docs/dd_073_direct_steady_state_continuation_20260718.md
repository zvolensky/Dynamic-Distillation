# DD-073: Direct Steady-State Continuation

Date: 2026-07-18

## Purpose

DD-072 established that the direct `281 x 281` conserved steady-state system
is finite, conservative, structurally and numerically full rank, and suitable
for bounded nonlinear work. DD-073 implements the approved five-stage
continuation:

| Stage | Released unknowns and equations | Size |
|---:|---|---:|
| 1 | Local thermo/phase states and local reconstruction/volume/equilibrium | `160` |
| 2 | Conserved component/internal-energy states and steady balances | `240` |
| 3 | Liquid flows and uncapped Francis hydraulics | `258` |
| 4 | Vapor flows and uncapped pressure-drop closure | `277` |
| 5 | `D`, `B`, `Q_C`, `Q_R` and four operating specifications | `281` |

The implementation uses additive-log-ratio composition coordinates,
logarithmic positive-variable coordinates, scaled affine temperature and
energy coordinates, bounded trust-region least squares, colored central
finite differences, deterministic adaptive lambda steps, accepted-state
retention, rank/condition gates, and optional uncolored endpoint checks.

## Implementation Verification

Focused tests verify:

- exact stage counts `160`, `240`, `258`, `277`, and `281`;
- homotopy endpoint identities;
- transform round trips;
- composition simplex and positive-variable preservation;
- adaptive step growth, reduction, and minimum-step stop;
- conservation telescoping;
- colored/uncolored transformed-Jacobian identity;
- exact reuse of the DD-072 physical residual at `lambda=1`.

No clipping, projection, imported-profile substitution, or artificial phase
transfer is used.

## Live DWSIM Results

Two live DWSIM PR paths were attempted from the ChemSep seed.

The first oriented local anchors by broad residual family. It accepted 22
continuation points through `lambda=0.6173584`, retained rank `160/160`, and
retained component and energy telescoping. At the minimum permitted step it
stopped with homotopy infinity norm `6.91e-4`.

A derivative audit found that 20 last-component reconstruction rows had been
given the wrong anchor orientation for their paired liquid ALR coordinate. A
single corrected attempt fixed that generic orientation rule and added a
regression test. The corrected path accepted through `lambda=0.377734375`,
again with rank `160/160`, exact conservation, no safeguards, and no
coordinate saturation. It stopped at the minimum step with homotopy infinity
norm `1.08e-5`. No retry changed solver tolerances or model parameters.

The corrected live report is:

- `logs/direct_steady_state_continuation_r2_20260718.json`
- `logs/direct_steady_state_continuation_r2_20260718.md`
- `logs/direct_steady_state_continuation_r2_20260718_states.npz`

## Endpoint Diagnosis

The Stage 1 physical Jacobian, evaluated separately at `lambda=1`, remains
full rank at both the ChemSep state and the last accepted state:

| State | Rank | Condition estimate |
|---|---:|---:|
| ChemSep | `160/160` | `5.21e6` |
| Last accepted first path | `160/160` | `4.89e6` |

Thus the continuation stop is not a structural or local numerical-rank loss.

A bounded direct Stage 1 endpoint diagnostic was then run with the same
transformed coordinates and physical residuals. Sparse `LSMR` stopped at
scaled infinity norm `2.38e-4` with condition estimate `7.17e10`. An exact
dense trust-region linear solve stopped at scaled infinity norm `2.12e-4`
with condition estimate `2.17e10`. Both remained full rank and safeguard-free.

The residual floor is distributed across interior component reconstruction
and energy rows rather than being confined to the reflux drum. This is
consistent with the Stage 1 ordering holding ChemSep-derived component
inventories and internal energies fixed while changing phase compositions,
temperature, pressure, and phase amounts to the DWSIM equilibrium basis.
Full rank does not prove that those fixed conserved anchors admit an exact
positive two-phase local state.

## Decision

Classification: `dd073_stage1_local_closure_not_resolved`.

DD-073 stops at Stage 1. No Stage 2 through Stage 5 solve, direct steady-state
root, serialization, or dynamic test is authorized.

Do not lower the `1e-7` homotopy gate, reduce the minimum lambda step, or tune
additional anchor signs. Two lambda paths and two endpoint linear solvers
already demonstrate that such tuning would be an open-ended numerical
campaign.

The next formulation must change the release ordering so conserved component
and energy states can move consistently with phase-state reconciliation.
Defensible options are:

1. merge the current local and conserved-state releases into one square
   `240 x 240` continuation stage; or
2. formulate a dedicated local UV initialization whose conserved anchors are
   generated on the same DWSIM basis, with any mapping replacement reported
   explicitly and not counted as optimizer movement.

Either option requires a new structural and endpoint-identity audit before a
live solve. The final `281 x 281` DD-072 target equations remain unchanged.

## Evidence

- `src/dynamic_distillation/direct_steady_state_continuation_v1.py`
- `tools/solve_direct_steady_state_continuation.py`
- `tests/test_direct_steady_state_continuation_v1.py`
- `logs/direct_steady_state_continuation_20260718.json`
- `logs/direct_steady_state_continuation_r2_20260718.json`
