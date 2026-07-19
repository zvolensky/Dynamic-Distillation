# DD-089 DWSIM PR Interface-Consistency Study

## Purpose

DD-089 is a standalone property-provider investigation authorized after
DD-088. It does not revise DD-088, rerun its root campaign, or authorize
dynamics.

The study asks whether the `1.46702e-5` DD-088 composition discrepancy is:

- a repeatable difference between DWSIM interfaces;
- sensitivity near the bubble boundary;
- a consequence of using overall composition with flash-derived `K` values;
- or an inconsistency unsupported by an independent Peng-Robinson calculation.

## Frozen State

The exact DD-088 drum state is read from the committed result:

```text
T = 133.7132934933824 F
P = 218.44 psia
x = [0.7030012030418336, 0.2836055267843538, 0.013393270173812703]
y_bubble = [0.851276948235418, 0.14519622244218763, 0.0035268293223943673]
```

Both DD-088 artifacts are protected by SHA-256 checks.

## Frozen Execution

Three fresh Python/DWSIM processes evaluate the same predefined samples in
forward, reverse, and deterministic interleaved order.

The samples include:

- the exact preserved state;
- an independent re-solve of the same bubble state;
- fixed-temperature offsets of `+/-0.001`, `+/-0.01`, and `+/-0.1 F`;
- bubble-manifold pressure offsets of `+/-0.01` and `+/-0.1 psia`;
- bubble-manifold additive-log-ratio composition offsets of `+/-1e-4`.

Each evaluation records:

- raw TP-flash `x`, `y`, and `K`;
- imposed-phase fugacity residuals;
- Rachford-Rice vapor fraction;
- `normalize(K*z)` using overall composition;
- `normalize(K*x_flash)` using flash liquid composition;
- lever-rule and vector-decomposition closure;
- fresh-process repeatability;
- an independent PR bubble calculation using frozen DWSIM constants and
  interaction parameters but separately implemented equations.

## Restrictions

DD-089 shall not:

- evaluate a column residual;
- execute or alter the DD-088 root solver;
- modify the `40 x 40` equations;
- revise the DD-088 tolerance;
- repair a checkpoint;
- integrate dynamics.

The resulting diagnostic references are prospective. They cannot convert
DD-088 into a pass.
