# DD-224 DD-223 Diagnostic-Evidence Audit

## Plain-Language Result

DD-223 saved enough information to prove that the root solve failed, but not
enough to explain exactly which equations caused the failure.

The saved artifact contains both endpoint coordinates, physical states, block
residual summaries, Jacobian ranks, condition numbers, and singular values.
It does not contain:

- each individual endpoint residual;
- either complete endpoint Jacobian matrix.

Without the matrices, the weakest equation and variable combinations cannot be
calculated. Singular values show how severe the problem is, but not where it
lives.

## Decision

One read-only replay of the two saved endpoints is authorized. It must use the
same DWSIM PR model, coordinates, scales, 15-color Jacobian, and finite-
difference steps. It may record complete residual vectors and matrices only.
It may not solve, alter a state, advance time, or run dynamics.

DD-223 remains failed and cannot be retried.
