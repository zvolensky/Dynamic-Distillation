# External Review Package

Package: `external_review_coupled_inventory_closure_20260717`

Date: 2026-07-17

## Start Here

Send `REVIEWER_PROMPT.md` with this package. The reviewer should then read
`PROBLEM_STATEMENT.md` and inspect `EVIDENCE_SUMMARY.csv`.

The core result is:

- the previous rate gate passed a 2400-second run with a score of `0.3804`;
- the run was losing `533.79 lbmol/h` of modeled inventory;
- numerical mass conservation was effectively exact;
- an experimental local phase-transfer closure zeroed tray vapor-total
  residuals but left the global inventory loss unchanged;
- the local closure is rejected;
- the corrected steady-state gate now fails this state.

The requested review is whether the runtime model needs a coupled
algebraic/DAE closure across pressure, vapor flow, phase generation, energy,
and liquid flow/inventory.

## Package Map

- `PROBLEM_STATEMENT.md`: self-contained technical statement and review
  questions.
- `REVIEWER_PROMPT.md`: comprehensive review assignment, requested analyses,
  constraints, and response format.
- `EVIDENCE_SUMMARY.csv`: headline results from the included runs.
- `MANIFEST.csv`: file list, sizes, and SHA-256 hashes.
- `docs/`: current architecture, requirements, gates, issue history, and
  DD-060/DD-064 findings.
- `source/`: runtime RHS, scaffold, thermo coordination/provider context, and
  project dependencies.
- `tests/`: focused tests covering equilibrium relaxation, the experimental
  closure, and the global inventory gate.
- `inputs/`: workbook seed and optimizer summary used by this line of runs.
- `runs/reference_2400s/`: previous low-score reference endpoint and time
  series.
- `runs/one_step_control/`: matched control without local closure.
- `runs/one_step_candidate/`: matched candidate with local closure.
- `runs/candidate_60s/`: bounded 60-second closure probe.
- `runs/global_inventory_gate_proof/`: proof that the corrected gate rejects
  the materially unsteady state.
- `tools/`: current K-state audit utility for supporting consistency review.

## Important Exclusions

The reference startup trace is about `1.75 GB`, and the 60-second candidate
trace is about `42 MB`. They are excluded to keep this package reviewable.
Compact profile/summary CSVs, metadata, checkpoints, and restart workbooks are
included instead.

## Source State

The package was built from branch `refactor/compute-efficiency`, base commit
`06a7563`. The included source contains uncommitted work made after that
snapshot; reviewers should treat the packaged source files and manifest
hashes as the authoritative reviewed state.
