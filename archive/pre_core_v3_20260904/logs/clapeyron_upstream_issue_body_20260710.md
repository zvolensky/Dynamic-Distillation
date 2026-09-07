## Summary

For a Peng-Robinson C3-C5 mixture that Clapeyron's own bubble/dew calculations identify as single liquid phase, `tp_flash` and `Clapeyron.tp_flash2` return two composition rows. The second row has zero phase fraction/moles and duplicates the first composition exactly.

A downstream caller that treats the row count as the phase count therefore sees two phases and computes `K = y ./ x = [1, 1, 1]`. I would appreciate guidance on the intended return contract and, if appropriate, a less ambiguous result or documented phase-status API.

This report is related in symptom to #465 (trivial/unit-K flash results), but I am **not** claiming incorrect phase classification here: the bubble/dew checks below support a single liquid phase.

## Minimal reproducible example

```julia
using Clapeyron

model = PR(["n-Propane", "n-Butane", "n-Pentane"])

p = 1.6005646620614817e6  # Pa
T = 329.8433241022147     # K
z = [
    0.5387358764517459,
    0.41587305276545855,
    0.04539107078279546,
]

x, n, G = tp_flash(model, p, T, z)
r = Clapeyron.tp_flash2(model, p, T, z)

println("tp_flash compositions = ", x)
println("tp_flash phase moles = ", n)
println("K from returned rows = ", vec(x[2, :]) ./ vec(x[1, :]))
println("tp_flash2 fractions = ", r.fractions)
println("tp_flash2 compositions = ", r.compositions)
println("tp_flash2 volumes = ", r.volumes)

println("bubble_temperature = ", bubble_temperature(model, p, z)[1])
println("dew_temperature = ", dew_temperature(model, p, z)[1])
```

## Actual output

```text
tp_flash compositions =
[0.538735876451746  0.4158730527654586  0.045391070782795466;
 0.538735876451746  0.4158730527654586  0.045391070782795466]

tp_flash phase moles =
[0.5387358764517459  0.41587305276545855  0.04539107078279546;
 0.0                 0.0                  0.0]

K from returned rows = [1.0, 1.0, 1.0]

tp_flash2 fractions = [0.9999999999999999, 0.0]
tp_flash2 compositions =
[[0.538735876451746, 0.4158730527654586, 0.045391070782795466],
 [0.538735876451746, 0.4158730527654586, 0.045391070782795466]]
tp_flash2 volumes =
[0.00010183576606635026, 0.00010183576606635026]

bubble_temperature = 341.90662976792436
dew_temperature = 356.0940823479843
```

Since `T = 329.843 K` is below the calculated bubble temperature at this pressure, the single-liquid result itself appears internally consistent. The ambiguity is that the returned arrays still have two rows and the inactive row is an exact duplicate.

## Downstream impact

In a dynamic equilibrium-stage model, we initially:

1. inferred phase count from the number of returned composition rows;
2. selected liquid/vapor rows using phase properties;
3. computed `K = y ./ x`.

The zero-fraction duplicate row made the result look two-phase and produced exact unit K-values. Across a focused set of 54 PR flash calls at C3-C5 column states, this occurred in 40 calls. Scalar and batched calling paths agreed, so it was not a cache or batching discrepancy.

For comparison only, another PR implementation exposes non-unit equilibrium/stability K-values at the fixed point:

```text
[1.3815217726803446, 0.58257950518798, 0.29621552047336774]
```

I understand that values can differ because parameter databases and binary interaction parameters may differ; the comparison is included to explain why a downstream model expected useful non-unit K-values even when the stable flash result is single phase.

## Questions / requested remediation

1. Is the duplicate zero-fraction phase the intended `MichelsenTPFlash` return contract for a single-phase state?
2. Is filtering `r.fractions` by a tolerance the canonical way to determine the active phase count?
3. What is the recommended Clapeyron API for obtaining incipient/opposite-phase compositions or equilibrium K-values at a single-phase `T, p, z` state?
4. If this behavior is intended, could the `tp_flash` documentation explicitly warn that the number of composition rows is not necessarily the number of active phases?
5. Alternatively, could single-phase results return one active row or expose an explicit phase-status/active-phase indicator?

## Environment

- Julia: `1.12.6`
- Clapeyron.jl: `0.6.26`
- OS: Windows
- Model: `PR` with Clapeyron's standard component database
