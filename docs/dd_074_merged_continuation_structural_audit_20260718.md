# DD-074: Merged Continuation Structural Audit

Date: 2026-07-18

## Purpose

DD-074 is the final bounded test of the manual release-order continuation
architecture. It merges DD-073's local and conserved-state stages, audits the
resulting physical dependency graph, and authorizes one live DWSIM attempt
only if every structural and endpoint gate passes.

No nonlinear or live DWSIM solve is part of the structural gate.

## Proposed Stages

The stage definitions are generated from the DD-071 registry:

| Stage | Active physical system | Size |
|---:|---|---:|
| A | Local thermo/phase and conserved `N/U`; local closure and steady balances | `240 x 240` |
| B | Add liquid flows and Francis hydraulics | `258 x 258` |
| C | Add vapor flows and pressure-drop closure | `277 x 277` |
| D | Add `D`, `B`, `Q_C`, `Q_R` and operating specifications | `281 x 281` |

The merged physical residual accounting is:

- component reconstruction: `60`;
- internal-energy reconstruction: `20`;
- occupied-volume closure: `20`;
- equilibrium: `60`;
- steady component balances: `60`;
- steady energy balances: `20`.

This totals `240`. The DD-071 registry contains `60`, not `40`, equilibrium
rows for 20 two-phase nodes and three components. No filler or duplicate
equation is introduced.

## Identity Anchors

DD-074 removes DD-073's residual-family pairing and sign table. New variables
and new residual rows retain their independent registry ordering, and the
lambda-zero anchor vector is exactly the transformed solver-coordinate
vector. Therefore:

`dA/dw = I`

at the anchor endpoint. Every anchor sign is `+1`.

Schema `dd074-merged-continuation-v1` is required for any future DD-074
restart. DD-073 state archives have no such schema and are rejected.

## Structural Results

| Stage | Count | Physical structural rank | Nullity | Empty rows | Unused columns |
|---:|---:|---:|---:|---:|---:|
| A | `240` | `239` | `1` | `0` | `0` |
| B | `258` | `258` | `0` | `0` | `0` |
| C | `277` | `277` | `0` | `0` | `0` |
| D | `281` | `281` | `0` | `0` | `0` |

The deterministic matching identifies:

- unmatched unknown: `NV[partial_reboiler]`;
- unmatched residual: `component_balance[partial_reboiler,n-Pentane]`.

All conserved `N/U` variables have graph paths to their local reconstruction
and associated steady-balance rows. The failure is not an empty row, unused
column, missing owner, duplicate equation, or anchor defect. The `240 x 240`
physical subgraph itself is structurally singular.

The fact that Stage B recovers full rank means liquid-flow/hydraulic variables
provide coupling absent from the proposed merged endpoint. Folding those
variables into another first-stage variant would be precisely the DD-075
release-order iteration prohibited by the predefined stop rule.

## Endpoint And Conservation Checks

- lambda-zero identity maximum error: `0`;
- merged lambda-one DD-072 identity maximum error: `0`;
- final lambda-one DD-072 identity maximum error: `0`;
- component telescoping maximum relative error: approximately `1.91e-16`;
- energy telescoping relative error: approximately `2.72e-16`;
- variable identity anchors: pass;
- restart schema rejection: pass.

These checks confirm that the structural failure is not caused by a changed
physical target or conservation assembly.

## Decision

Classification:
`dd074_structural_gate_failed_manual_continuation_retired`.

The DD-074 merged stage fails the required `240/240` structural-rank gate.
Therefore:

- no live merged-stage DWSIM solve is authorized or attempted;
- no tolerance, anchor, scaling, minimum-step, or solver change is permitted;
- no `258`-first or other DD-075 release-order variation is permitted;
- manual staged continuation is retired.

The next work must pivot architectures. Defensible candidates are:

1. pseudo-transient continuation on the complete conserved `281 x 281`
   physical system;
2. a full-system nonlinear/DAE solver with analytic or automatic derivatives;
3. a reduced-column validation model before returning to the full column;
4. a dedicated feasibility study of whether equilibrium, volume, and
   hydraulic equations admit a common physical operating point.

This is a stop decision, not evidence that the final `281 x 281` physical
system is structurally defective. DD-071 and DD-072 already establish that
the complete system is structurally and numerically full rank.

## Evidence

- `src/dynamic_distillation/direct_steady_state_continuation_v1.py`
- `tools/audit_merged_steady_state_continuation.py`
- `tests/test_direct_steady_state_continuation_v1.py`
- `logs/direct_steady_state_merged_structure_20260718.json`
- `logs/direct_steady_state_merged_structure_20260718.md`
