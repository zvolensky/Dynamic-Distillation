# DD-092 Core V3 Provider-Governed Numerical Audit

Date: 2026-07-19

## Decision

DD-092 passes its single frozen live execution.

The independently implemented Core V3 residual preserves the DD-091
structure under live DWSIM PR evaluation. Both precommitted states retain:

- numerical rank `40/40` at `h=1e-5` and `h/2=5e-6`;
- local condenser bubble rank `3/3` at both steps;
- condition below the frozen `1e8` hard stop;
- no zero row, zero column, or coupling outside the DD-091 graph;
- component and energy telescoping near machine precision;
- valid positive states, flows, and tray liquid heights;
- negative condenser duty;
- strict direct-fugacity bubble closure;
- coherent diagnostic TP-flash phase algebra;
- agreement with the validation-only independent PR implementation;
- no clipping, projection, property fallback, or provider-policy violation.

This result authorizes drafting and precommitting one bounded three-start
Core V3 steady-root contract. It does not authorize executing that solve,
deriving a dynamic mass matrix, or integrating dynamics.

## Frozen Execution

- Contract commit: `1ffa504beda0df0c805260401c9d7a5f70cf98cb`
- Contract payload SHA-256:
  `ca4f8728bda6b3981d7a1dca9e8a42eee096cf7ed88356852a0d139e8a05311b`
- Execution count: one
- Wall clock: `11.034 s`
- Property package: DWSIM Peng-Robinson
- Full nonlinear solve attempted: no
- Root imported: no
- Mass-matrix derivation attempted: no
- Dynamic integration attempted: no

## Numerical Results

| Metric | Canonical | Perturbed | Gate |
|---|---:|---:|---:|
| Scaled residual infinity norm, diagnostic | `3.978625e-1` | `3.966443e-1` | reported only |
| Rank at `h=1e-5` | `40/40` | `40/40` | `40/40` |
| Rank at `h/2=5e-6` | `40/40` | `40/40` | `40/40` |
| Condition at `h` | `2.732091e6` | `2.733414e6` | `<1e8` |
| Condition at `h/2` | `2.589033e6` | `2.733411e6` | `<1e8` |
| Local bubble rank at both steps | `3/3` | `3/3` | `3/3` |
| Direct bubble residual infinity norm | `1.332268e-15` | `1.221245e-15` | `<1e-10` |
| Component telescoping relative error | `1.790538e-16` | `2.291889e-16` | `<1e-12` |
| Energy telescoping relative error | `3.386408e-17` | `1.861954e-16` | `<1e-10` |
| TP-flash vapor fraction | `4.459380e-4` | `4.456931e-4` | `<=1e-3` |
| Independent PR bubble temperature difference, F | `3.609037e-5` | `3.608853e-5` | `<1e-3` |
| Independent PR vapor-composition max difference | `1.326779e-9` | `1.324430e-9` | `<1e-6` |
| Condenser duty, BTU/h | `-5.500357e7` | `-5.502040e7` | negative |

The diagnostic residual is not expected to be small. The two frozen points
are physically evaluable seeds displaced from steady balance; DD-092 asks
whether the residual and Jacobian are complete, conservative, correctly
owned, and numerically usable. It does not ask whether either seed is a root.

The canonical residual is dominated by the known source-profile versus
Francis-hydraulics mismatch, not by a rank loss or provider inconsistency.

## Provider Ownership

The execution recorded `7,234` property requests across residual, Jacobian,
diagnostic, and validation evaluations with no policy violation.

- Direct imposed-phase DWSIM fugacity owns all governing equilibrium rows.
- Declared DWSIM phase enthalpy owns energy properties.
- Declared DWSIM liquid density owns Francis hydraulics.
- TP flash runs only after residual and Jacobian evaluation as a diagnostic.
- Parameter-aligned independent PR runs only as validation.
- No interface fallback is available.
- No mixed-basis `K_flash*z` gate is evaluated.
- Direct bubble vapor composition is not required to equal TP-flash vapor
  composition.

For both states, TP-flash `K*x_flash` identity is exact and lever-rule closure
is at roundoff. The small nonzero vapor fraction is within the prospectively
frozen near-boundary tolerance and does not classify the drum as stable
vapor.

## Authorization

The next permitted artifact is a separate, frozen Core V3 root-solve
contract containing:

1. exactly three complete starts;
2. fixed coordinates, scales, physical bounds, solver, Jacobian rules, and
   evaluation budget;
3. common-root, residual, rank, conditioning, conservation, phase, physical,
   bound-activity, and provider-provenance gates;
4. a hard stop that prohibits post-result solver, tolerance, bound, topology,
   duty, or provider variation.

DD-092 itself performs and authorizes no steady solve or dynamic work.
