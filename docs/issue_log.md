# Issue Log

Updated: 2026-02-21 19:20 (local)
Source: this chat session and related run outcomes referenced during the session.

| Issue ID | Identified Date | Issue | Status | Notes |
|---|---|---|---|---|
| `DD-001` | 2026-02-17 | Table-thermo simulations were too slow for practical iteration. | `Mitigated` | Parallel table thermo workers were implemented/used (`table-pool`), improving throughput. |
| `DD-002` | 2026-02-17 | Summary log pressure PV did not always match the actual pressure-controller PV source. | `Resolved` | Summary now prefers `P_top_ctrl_pv_psia` from runtime diagnostics. |
| `DD-003` | 2026-02-17 | Total-condenser intent (`V_to_top_drum=0`) was violated in some runs. | `Partially Resolved` | Strict zero-slip behavior was added for total-condense split logic; coupled pressure/duty modes can still create behavior that needs further rationalization. |
| `DD-004` | 2026-02-17 | Distillate drum pressure exhibited unrealistic spikes/drops during startup. | `Open` | PSV and startup conditioning reduced some spikes but did not deliver stable realistic startup behavior across scenarios. |
| `DD-005` | 2026-02-17 | Distillate quality control trend was counterintuitive (reflux behavior vs purity drift). | `Open` | Even after ChemSep warmer-feed re-alignment and `xD_SP=0.0951`, 600 s full-dynamic runs showed upward C4 drift in both cap-on and cap-off cases. |
| `DD-006` | 2026-02-17 | Model does not reliably approach a credible steady-equilibrium region under target conditions. | `Open (Critical)` | Persists across control strategies and thermo sources; remains primary unresolved issue. |
| `DD-007` | 2026-02-17 | Thermo table behavior diverged from expected PR-based behavior in dynamic context. | `Open` | Local/high-resolution table ideas were explored, but convergence issues remain. |
| `DD-008` | 2026-02-17 | Nontrivial stage/global conservation residuals (mass/energy) observed during problematic runs. | `Resolved` | Conservation residuals now consistently approach machine precision (~1e-14 BTU/s for energy, <0.006 lbmol/h for mass). Model includes proper feed enthalpy closure and comprehensive diagnostics. |
| `DD-009` | 2026-02-17 | Pressure-loop stabilization additions (PV filter, gain damping, slew limits) did not materially improve equilibrium outcome. | `Verified - No Material Improvement` | Mitigation was implemented and tested; behavior stayed effectively unchanged for convergence objective. |
| `DD-010` | 2026-02-17 | Condenser mode intent was initially misaligned with case assumptions (total condenser operation). | `Resolved` | Run configuration and interpretation were corrected to treat the unit as total condenser where required. |
| `DD-011` | 2026-02-19 | Initialization parity breaks when geometry-driven liquid hydraulics overrides internal ChemSep liquid profile, causing strong nonphysical drift. | `Open (Critical)` | Input parity to `ChemSep Depropanizer_warmer_feed.xls` was re-verified (stage-profile deltas effectively zero), but 600 s fully dynamic runs still drift materially. Cap-off improved composition residual trend but increased top-pressure drift. Root-cause report: `docs/dd_011_hydraulic_parity_drift_report_2026-02-19.md`. Follow-up: `docs/dd_011_hydraulic_parity_followup_2026-02-21.md`. |
