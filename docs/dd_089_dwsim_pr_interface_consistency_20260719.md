# DD-089 DWSIM PR Interface-Consistency Result

## Decision

DD-089 identifies the mechanism behind the sole DD-088 rejection.

The original DD-088 diagnostic compared the directly solved bubble vapor
composition with:

```text
normalize(K_flash * z_overall)
```

However, DWSIM's returned flash `K` values are exactly:

```text
K_flash = y_flash / x_flash
```

At the preserved state, the TP flash reports a small but nonzero vapor
fraction. Therefore, its liquid composition `x_flash` is not the overall
composition `z_overall`. Substituting `z_overall` into `K_flash*x` mixes two
different composition bases.

This is not the whole story. A separate, deterministic difference also exists
between the direct bubble vapor and the TP-flash vapor. The two vector effects
oppose one another and partially cancel in the original DD-088 scalar metric.

## Frozen Execution

Contract commit `fcf3237` fixed:

- the exact DD-088 endpoint;
- 16 samples per process;
- three fresh Python/DWSIM processes;
- forward, reverse, and interleaved evaluation orders;
- temperature, pressure, and composition perturbations;
- local bubble-solve settings;
- DWSIM PR constants and binary interactions;
- an independently implemented Peng-Robinson fugacity calculation;
- diagnostic rules and restrictions.

The study completed in `15.569 s`. It did not evaluate a column residual,
execute a column solve, alter DD-088, or integrate dynamics.

## Preserved State

```text
T = 133.7132934933824 F
P = 218.44 psia

z_overall =
[0.7030012030418336,
 0.2836055267843538,
 0.013393270173812703]

y_direct =
[0.851276948235418,
 0.14519622244218763,
 0.0035268293223943673]
```

DWSIM TP flash returns:

```text
x_flash =
[0.7029057049489177,
 0.28369466926628817,
 0.01339962578479408]

y_flash =
[0.8512341456813639,
 0.14523781693929755,
 0.0035280373793385527]

beta = 6.438286e-4
```

## Decomposition

The original comparison decomposes exactly as:

```text
y_direct - normalize(K*z_overall)
  = (y_direct - y_flash)
  + (y_flash - normalize(K*x_flash))
  + (normalize(K*x_flash) - normalize(K*z_overall))
```

At the preserved state:

| Term | Maximum absolute value |
|---|---:|
| Original DD-088 metric | `1.467021e-5` |
| Direct bubble `y` minus TP-flash `y` | `4.280255e-5` |
| TP-flash `y` minus `normalize(K*x_flash)` | `4.336809e-19` |
| Flash-liquid versus overall-composition basis effect | `5.747276e-5` |
| `x_flash-z_overall` | `9.549809e-5` |
| Vector decomposition closure | `0.0` |
| Lever-rule material closure | `4.773959e-15` |

The `5.747e-5 / 1.467e-5` ratio is about `3.92`, but it is not a fractional
partition: the basis effect and direct-versus-flash effect have opposing
signs and partially cancel.

## API Findings

The TP flash is internally coherent:

- `K_flash*x_flash` reproduces `y_flash` to roundoff;
- the Rachford-Rice vapor fraction reconstructs `z_overall` from
  `x_flash/y_flash` to `4.8e-15`;
- all three fresh processes return identical values despite different call
  orders.

The two DWSIM property paths do not agree to the frozen DD-088 composition
tolerance near this bubble boundary:

- direct imposed-phase bubble fugacity residual: `3.89e-15`;
- TP-flash phase pair re-evaluated through imposed-phase fugacity:
  `1.14e-4`;
- direct bubble vapor versus TP-flash vapor: `4.28e-5`.

This behavior persists over the frozen pressure and composition neighborhood.
It is deterministic rather than random numerical noise.

## Independent PR Check

The independent calculation uses DWSIM's frozen component constants and
binary interaction parameters but separately implemented Peng-Robinson
equations and root selection.

At the preserved state, relative to the direct imposed-fugacity bubble:

```text
independent PR bubble temperature difference = 3.825286e-5 F
independent PR vapor maximum difference       = 4.339660e-9
```

The same agreement persists along the frozen bubble-manifold pressure and
composition perturbations.

This strongly supports the direct imposed-phase fugacity solution. It does
not prove that DWSIM's TP flash is thermodynamically defective; the remaining
difference may reflect flash convergence criteria, endpoint conventions, or
the interface's handling of a very small second phase.

## Interpretation

DD-088's failed diagnostic was not a pure comparison of two estimates of the
same quantity:

1. It applied flash-derived `K` values to overall composition rather than the
   flash liquid composition from which those `K` values were formed.
2. That basis substitution contributed `5.75e-5`.
3. A separate `4.28e-5` direct-bubble versus TP-flash endpoint difference
   opposed it.
4. Their partial cancellation produced the observed `1.467e-5`.

For a prospective architecture, direct imposed-phase fugacity equations are
the defensible equilibrium authority. TP flash may be used for phase-region
classification and material split, but its near-boundary phase composition
should not be imposed as a `1e-5` acceptance oracle against that authority
without an independently validated provider tolerance.

## Authorization

DD-088 remains formally failed and retired. DD-089 does not authorize:

- rerunning or reclassifying DD-088;
- altering the retired `40 x 40` system;
- dynamic integration;
- using the DD-088 root as an accepted initializer.

DD-089 does authorize a project decision on whether to define a prospective
provider contract for a materially new architecture. Such a contract should
declare:

- direct fugacity equilibrium as primary;
- TP flash phase classification and lever-rule closure as independent checks;
- flash compositions interpreted on the flash phase bases;
- provider tolerances established prospectively from standalone evidence.

Primary evidence:

- `logs/dd089_dwsim_pr_interface_consistency_contract_20260719.json`
- `logs/dd089_dwsim_pr_interface_consistency_20260719.json`
