# DD-174 Moving-Step Physical-Scale Adjudication Contract

## Purpose

DD-173 remains a formal failure because its frozen per-component relative
inventory-refinement limit was exceeded. DD-174 may not change that result.
It performs one zero-call adjudication of the immutable DD-173 full-step and
refined endpoints to determine whether their difference is small on declared
physical inventory scales.

## Frozen Inputs

- DD-173 contract and result files, protected by SHA-256 digests;
- the accepted DD-169 initial component inventories;
- DD-173's saved full `1.0 s` endpoint;
- DD-173's saved second `0.5 s` endpoint;
- DD-173's saved response and conservation evidence.

No endpoint may be regenerated. Model, provider, and solver calls are all
prohibited.

## Frozen Gates

| Metric | Required limit |
|---|---:|
| Maximum absolute component difference | `< 1.0e-4 lbmol` |
| Maximum component difference relative to `max(initial, 1 lbmol)` | `< 1.0e-5` |
| Maximum component difference relative to its volume's total holdup | `< 1.0e-6` |
| L1 component difference | `< 2.0e-4 lbmol` |
| Absolute signed total-inventory difference | `< 1.0e-9 lbmol` |
| Inherited DD-173 total-response refinement difference | `< 1.0e-6 lbmol` |
| Inherited global component-identity error | `< 1.0e-6 lbmol` |

The source must remain the unchanged DD-173 result, with inventory refinement
as its only failed refinement gate and no failed root or response gate.

## Decision

A complete pass authorizes only one separately frozen smaller-timestep moving
proof. It does not authorize a trajectory and does not reclassify DD-173. A
failure stops the seven-volume moving-dynamics path.
