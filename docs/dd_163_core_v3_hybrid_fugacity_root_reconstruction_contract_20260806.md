# DD-163 Frozen Hybrid Fugacity Root-Reconstruction Contract

- Payload SHA-256: `cb6cd3c6c1295a0088e7c18989fbb143a541e3bc302e1fec2b797340a5d8ce22`
- Start: exact accepted DD-160 DWSIM zero-time root
- Solve: one captured modified-Newton reconstruction on the hybrid basis
- Jacobian: one frozen colored central difference at `1e-5`
- Endpoint: independent residual/Jacobian, physicality, conservation, and engineering-equivalence audit
- Retry, fallback, clipping, projection, timestep, or trajectory: prohibited

Passing authorizes only integration of the hybrid provider into a separately frozen trajectory contract.
