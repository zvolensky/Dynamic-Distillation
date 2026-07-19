# DD-093 Core V3 Steady-Root Campaign Contract

Date: 2026-07-19

## Purpose

DD-093 defines exactly one bounded three-start nonlinear campaign for the
unchanged DD-092 Core V3 `40 x 40` residual. This contract does not execute
that campaign.

## Architecture

The campaign retains prescribed pressure, feed, reflux, and reboiler duty;
solved signed-affine condenser duty; four energy-owned vapor links; direct
imposed-phase fugacity equilibrium; a saturated-liquid condenser boundary;
Francis-only liquid hydraulics; solved products; specified terminal amounts;
DD-090 provider authority; and DD-092 scales and dependency graph.

Core V2 residual ownership, DD-088 roots or status, profile forcing,
relaxation, flow caps, controllers, clipping, projection, and property
fallback are prohibited.

## Fixed Solver

```text
scipy.optimize.least_squares
method = trf
ftol = 1e-12
xtol = 1e-12
gtol = 1e-12
max_nfev = 500
x_scale = 1.0
```

The solve Jacobian is the uncolored central difference at `h=1e-5`.
Endpoint audits use `h=1e-5` and `h/2=5e-6`. No alternate solver,
continuation, restart policy, adaptive scaling, analytic-Jacobian experiment,
or post-result tuning is permitted.

## Frozen Starts

1. Exact DD-092 canonical Core V3 vector.
2. Exact DD-092 deterministic combined perturbation.
3. A fully independent smooth five-volume profile.

The third start changes the drum and every interior volume. It uses a
deterministic smooth ALR liquid profile between separately selected positive
terminal compositions, independently selected positive amounts and flows, a
separate direct-fugacity drum bubble reconstruction, and a separate
condenser-energy calculation of negative `Q_C`.

It uses no full residual, partial root solve, balance back-calculation,
continuation, endpoint from another start, DD-088 root or status, or ChemSep
acceptance target. All three complete 40-coordinate vectors are stored in the
contract JSON before campaign execution.

## Bounds

- temperature: `110 F` through `260 F`;
- terminal liquid amounts: `0.8` through `1.2` times target;
- interior liquid amounts: `0.2` through `2.0` times reference;
- all composition components: at least `1e-10`;
- internal flows: `0.1` through `5.0` times reference;
- each product: `1e-4 F` through `1.05 F`;
- condenser duty: `-3.0` through `-0.1` times
  `abs(Q_C_reference)`.

Physical bounds are converted once. An endpoint within `1e-6` transformed
units of any bound fails.

## Acceptance

Every start must terminate successfully; reach scaled residual below `1e-8`;
close governing fugacity below `1e-10`; retain full/local ranks `40/40` and
`3/3` at both steps; remain below condition `1e8`; preserve registered
coupling; keep both full and local singular-value spectra within `25%`
relative change between steps; preserve conservation; retain negative duty,
positive physical states,
drum temperature below its supplying stage, and physical tray heights; obey
provider ownership; pass direct bubble, independent PR, and TP-flash
diagnostics; and use no safeguard or fallback.

All three endpoints must agree in frozen physical coordinates below `1e-7`.

## Hard Stop

Any failed start or common-root gate retires this campaign. Failure does not
authorize another solver, changed tolerance, wider bound, duty or pressure
sweep, provider substitution, DD-088 root import, or dynamic work.

A later pass would authorize only a structural dynamic DAE contract. It would
not authorize integration.

## Current Authorization

Generate, test, commit, and push this contract and its three complete vectors.
Do not execute the nonlinear campaign.
