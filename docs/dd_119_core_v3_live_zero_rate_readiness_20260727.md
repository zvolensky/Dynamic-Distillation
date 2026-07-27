# DD-119 Core V3 Live Zero-Rate Readiness Audit

- Classification: `dd119_passed`
- Decision: `authorize_frozen_zero_rate_root_contract`
- Wall clock: `3.144 s`
- DWSIM calls: `7113`
- Canonical colored/full Jacobian difference: `0.000000e+00`
- DAE ranks: `[46, 46]`
- Terminal-augmented ranks: `[46, 46]`
- Augmented conditions: `[5622.221549867074, 5672.689535736832]`
- DAE-only conditions: `[2.540108e13, 3.755296e13]`
- Augmented spectrum changes: `[4.724158e-7, 4.496751e-7]`
- Canonical/refined residual infinity norms: `[0.0630019, 0.0586779]`
- Left-null residual projections: `[0.00760658, 0.00769831]`

All frozen numerical, structural, physical, conservation, provider, call, and wall gates pass. DD-119 performed no nonlinear solve or timestep.

## Interpretation

The DAE-only Jacobian is formally rank `46/46` at both states, but has two extremely weak directions. Adding the drum and sump total-holdup rows improves conditioning by roughly ten orders of magnitude without changing formal rank. The terminal rows therefore act as physically meaningful regularizers for near-scale freedoms.

The nonzero residual and left-null projections are diagnostics at unsolved starting states, not root failures. They do expose the central risk for the successor: the `48 x 46` system is overdetermined, so an exact root exists only if the two terminal holdup targets are compatible with the zero-rate DAE solution. One separately frozen two-start least-squares root campaign is authorized to answer that question. No dynamics is authorized.
