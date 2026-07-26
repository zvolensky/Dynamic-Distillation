# DD-102 Frozen Core V3 Pressure-Layer Numerical Contract

- Payload SHA-256: `465fbd97f94aa2133c594a24738621cd8224f7a656645890b307a8596a5e3727`
- Preparation base commit: `9f49fa7d273320616ffffde1b3c0f8de7da94002`
- System: `42 x 42` dynamic leading ledger with algebraic pressure
- States: accepted root pressure profile and one fixed ordered perturbation
- Jacobian steps: `1e-5`, `5e-6`
- Jacobian method: full central difference
- Provider-call ceiling: `10000`
- Live property evaluation during preparation: `False`
- Nonlinear solve during preparation: `False`
- Dynamic integration during preparation: `False`

## Decision rule

Both states must remain physical and conservative. All four Jacobians must be rank `42`, satisfy the fixed condition and spectrum gates, match the registered coupling pattern, and use only direct declared DWSIM properties. The pressure residual magnitude is diagnostic and will be reported without tuning.

A pass authorizes only one separately frozen nonlinear pressure-layer steady-root contract. It does not authorize integration, vapor holdup, or controllers.
