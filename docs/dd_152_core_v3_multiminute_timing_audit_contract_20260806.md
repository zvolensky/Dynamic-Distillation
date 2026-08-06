# DD-152 Frozen Zero-Call Multiminute Timing Audit Contract

- Payload SHA-256: `afe9bf3c4b6f0f9586812684296dc113ab791435363230c307fc7f0d65eb465b`
- Sources: immutable DD-150/DD-151 results and current frozen provider/parallel sources
- Work: static timing decomposition only
- Windows: 60 simulated seconds per coarse/refined segment
- Attribution: Jacobian, trajectory non-Jacobian, and outside-trajectory wall
- History test: first/last window ratio `>1.25` and root-order correlation `>0.50`
- Provider fact: exact-state density/Cp caches cap at 2,000 entries and clear wholesale
- DWSIM/provider/model/solver/state calls: prohibited
- Audit wall limit: `<120 s`

The audit may diagnose and recommend a bounded efficiency correction. It cannot authorize another trajectory.
