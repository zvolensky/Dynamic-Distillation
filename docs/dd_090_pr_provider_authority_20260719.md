# DD-090 PR Provider-Authority Result

## Decision

DD-090 passes.

The project now has a prospective, explicit thermodynamic authority contract
for a separately versioned successor architecture.

This result does not:

- reclassify DD-088;
- accept the DD-088 root as an initializer;
- revive the retired `40 x 40` architecture;
- authorize a column solve;
- authorize dynamic integration.

It authorizes only a project decision on whether to define a successor
architecture under the DD-090 property rules.

## Frozen Contract

Commit `752dad6` froze:

- 11 quantity ownership rules;
- direct-fugacity production authority;
- independent-PR validation authority;
- TP-flash phase-region and material-split authority;
- all prospective tolerances;
- mixed-basis prohibitions;
- no-fallback behavior;
- the immutable DD-089 evidence hashes.

Contract payload SHA-256:

```text
5d32cae013549350133ad814e668d060fec59da6857400e97c4cc66d41822192
```

The first execution command stopped before evidence evaluation because the
live Python dataclass contained tuples while the frozen JSON contained the
equivalent lists. Commit `35e3270` made the live payload JSON-native and added
a round-trip regression test. The frozen contract file, rules, tolerances,
evidence hashes, and payload checksum did not change.

The subsequent command performed the first and only evidence evaluation.

## Authority Hierarchy

### Direct imposed-phase fugacity

Primary production authority for:

- bubble/dew equilibrium;
- bubble temperature;
- incipient-phase composition;
- equilibrium-stage saturation;
- equilibrium residual acceptance.

Required residual:

```text
||r_f||inf < 1e-10
```

### Independent Peng-Robinson

Validation-only authority using the same constants, acentric factors, binary
interaction parameters, and documented PR root selection.

Required agreement:

```text
|delta T_bubble| < 1e-3 F
max|delta y|    < 1e-6
```

### DWSIM TP flash

Authority for:

- stable-phase classification;
- phase fraction;
- flash liquid and vapor compositions;
- flash `K=y_flash/x_flash`;
- Rachford-Rice and lever-rule reconstruction.

Required internal closure:

```text
max|y_flash-normalize(K*x_flash)| < 1e-12
max|z-((1-beta)*x_flash+beta*y_flash)| < 1e-12
```

At a directly solved bubble state:

```text
beta <= 1e-3
stable vapor = false
```

## Prohibited Uses

The contract prohibits:

- using `normalize(K_flash*z)` as a strict bubble-vapor oracle when beta is
  nonzero;
- requiring strict equality between direct incipient vapor and TP-flash
  vapor without a separately validated cross-interface tolerance;
- silently replacing direct fugacity with TP flash, or the reverse;
- using the independent PR implementation as a production property provider.

## Evidence

All frozen checks pass:

| Check | Evidence | Limit |
|---|---:|---:|
| Direct fugacity residual | `3.886e-15` | `<1e-10` |
| Independent PR temperature difference | `3.825e-5 F` | `<1e-3 F` |
| Independent PR vapor difference | `4.340e-9` | `<1e-6` |
| Flash `K*x_flash` reconstruction | `4.337e-19` | `<1e-12` |
| Flash lever-rule closure | `4.774e-15` | `<1e-12` |
| Bubble-region vapor fraction | `6.438e-4` | `<=1e-3` |
| Fresh-process spread | `0.0` | `<=1e-10` |
| Stable-vapor classification | `false` | required |
| Mixed-basis metric used as gate | `false` | required |
| Cross-interface vapor equality used as gate | `false` | required |
| Interface fallback used | `false` | required |

No live property call, column residual, nonlinear solve, checkpoint operation,
or dynamic integration occurred in DD-090.

## Next Decision

A successor architecture may now be proposed under a new version identity.
It may preserve governing equations demonstrated by DD-088, but it must adopt
DD-090's materially different property ownership and acceptance semantics.

The next increment should be an architecture contract only. It should decide:

- successor name and version boundary;
- which DD-088 equations are retained unchanged;
- how the DD-090 authority table enters residual and phase acceptance;
- structural unknown/equation ownership;
- pre-solve gates and hard stops.

No root campaign or dynamic mass-matrix work should begin until that contract
passes.

Primary evidence:

- `logs/dd090_pr_provider_authority_contract_20260719.json`
- `logs/dd090_pr_provider_authority_20260719.json`
