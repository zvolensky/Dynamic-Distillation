# DD-090 Prospective PR Provider-Authority Contract

## Purpose

DD-090 defines thermodynamic ownership for any successor architecture. It is
provider-only and prospective.

It does not:

- revise or rerun DD-088;
- evaluate the DD-088 root;
- alter the retired `40 x 40` equations;
- call DWSIM;
- evaluate a column residual;
- solve a column;
- integrate dynamics.

## Authority

### Direct imposed-phase fugacity

This is the production equilibrium authority for:

- bubble and dew temperature;
- incipient-phase composition;
- equilibrium-stage saturation;
- equilibrium residual acceptance.

The residual infinity norm must be below `1e-10`. No TP-flash fallback is
permitted.

### Independent Peng-Robinson

The parameter-aligned independent implementation is validation-only.

Prospective agreement requires:

```text
|delta bubble temperature| < 1e-3 F
max|delta incipient vapor| < 1e-6
```

It is not a production property provider.

### DWSIM TP flash

TP flash owns:

- stable-phase classification;
- phase fraction;
- `x_flash` and `y_flash`;
- `K_flash = y_flash/x_flash`;
- Rachford-Rice and lever-rule reconstruction.

Internal closure requirements are:

```text
max|y_flash-normalize(K_flash*x_flash)| < 1e-12
max|z-((1-beta)*x_flash+beta*y_flash)| < 1e-12
```

At a directly solved bubble boundary, `beta <= 1e-3` is a phase-region
tolerance, not an exact bubble equation.

## Prohibitions

`normalize(K_flash*z)` shall not be used as a strict bubble-vapor oracle when
`beta` is nonzero. Any resulting composition-basis approximation must be
reported separately.

No strict equality between direct incipient vapor and TP-flash vapor is
required until a separate cross-interface tolerance is validated.

No interface may silently replace another because their near-boundary results
disagree.

## Authorization

Passing DD-090 authorizes only a project decision on a separately versioned
successor architecture contract. It does not authorize a root solve or
dynamics.
