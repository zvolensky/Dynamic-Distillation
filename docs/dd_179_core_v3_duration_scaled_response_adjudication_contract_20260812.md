# DD-179 Duration-Scaled Response Adjudication Contract

## Purpose

DD-179 statically adjudicates only DD-178's inherited absolute response
ceiling. DD-178 remains formally failed and no state may be regenerated.

## Frozen Evidence

- immutable DD-178 contract and result, protected by SHA-256;
- coarse and refined actual total accumulation;
- path-integrated expected external-flow accumulation;
- global component identities and monotonicity flags;
- all non-response DD-178 campaign gates.

Model, provider, solver, and endpoint-regeneration calls are prohibited.

## Gates

- actual versus integrated expected response error `<1e-6` relative on each
  path;
- coarse/refined actual total-response difference `<1e-9 lbmol`;
- global component identity `<1e-6 lbmol` on each path;
- positive monotone response on each path;
- every non-response DD-178 campaign gate remains passing;
- DD-178's formal failure remains preserved.

## Prospective Policy

Future trajectory response bounds shall scale with integrated expected
external flow over the contract duration. A duration-independent absolute
maximum inherited from a shorter experiment shall not be used.

## Decision

A complete pass authorizes only one separately frozen longer open-loop
trajectory contract. Failure stops the physical-policy trajectory path.
