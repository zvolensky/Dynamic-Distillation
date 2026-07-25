# DD-097 Core V3 Implicit-Step Result

Date: 2026-07-25

## Decision

DD-097 passes every frozen gate in its single execution from contract commit
`ac43127`.

The Core V3 backward-Euler implementation preserves the exact DD-094 reduced
steady root, solves its simultaneous derivative/algebraic endpoint system,
and retains physicality and discrete conservation at both frozen step sizes.
This authorizes only a separately frozen short open-loop trajectory contract.

## Results

```text
zero-rate algebraic recovery
  residual infinity norm          6.941527e-12
  Jacobian rank                   23/23
  Jacobian condition              12.197547
  evaluations                     3
  algebraic movement              1.839509e-11

1.0 s backward-Euler step
  residual infinity norm          5.419607e-13
  Jacobian rank                   38/38
  Jacobian condition              35.132423
  evaluations                     2
  maximum component rate          7.612471e-8 lbmol/h
  relative inventory movement     9.927347e-13
  component conservation error    8.666203e-14
  energy conservation error       2.184282e-13

0.5 s backward-Euler step
  residual infinity norm          1.088933e-12
  Jacobian rank                   38/38
  Jacobian condition              35.192360
  evaluations                     3
  maximum component rate          7.776180e-8 lbmol/h
  relative inventory movement     5.185952e-13
  component conservation error    4.351723e-14
  energy conservation error       2.464925e-13

step refinement
  relative inventory difference   4.741395e-13
  rate-coordinate difference      3.120001e-13
  algebraic-coordinate difference 1.133552e-12
```

All physical checks pass: inventories and phase compositions remain positive,
temperatures remain ordered, liquid and vapor flows remain positive,
condenser duty remains negative, and hydraulic heights remain below tray
spacing. Storage bubble residuals remain below `3.78e-15`.

The campaign makes `44,686` governing DWSIM calls in `46.258 s`. Every call
uses direct imposed-phase fugacity, declared phase enthalpy, or declared
liquid density. No fallback or provider-policy violation occurs.

## Interpretation

This is a real implementation pass, not merely another structural result.
It confirms that:

- the positive inventory-rate map is internally consistent;
- exact stored-energy differences work inside the simultaneous step solve;
- the nonlinear solver reproduces the steady root without artificial motion;
- halving the step does not reveal a hidden numerical inconsistency;
- the live endpoint Jacobian remains well conditioned.

The result is intentionally limited. Both steps begin at an exact steady root
with unchanged inputs, so the physically correct outcome is essentially zero
motion. DD-097 therefore does not demonstrate transient response, attraction
back to the root, long-run stability, or controller behavior.

The property-call cost is also material. A multi-step implementation should
eventually avoid rebuilding every nested storage bubble Jacobian from scratch,
but performance optimization is not authorized before a bounded transient
correctness test.

## Next Authorized Increment

DD-098 may draft and precommit one short open-loop transient contract. A
defensible contract should include:

1. one unchanged-input root-hold trajectory;
2. one small, generic, predeclared perturbation that produces nonzero motion;
3. fixed total duration and `1.0 s`/`0.5 s` refinement runs;
4. per-step nonlinear convergence, physicality, conservation, provider, and
   refinement gates;
5. an immediate stop on any failed step, property call, or physical gate.

No controller tuning, initializer work, production tray scaling, pressure
dynamics, or vapor-holdup extension is authorized by DD-097.

Primary evidence:

- `logs/dd097_core_v3_implicit_step_contract_20260725.json`
- `logs/dd097_core_v3_implicit_step_20260725.json`
- `src/dynamic_distillation/core_v3/implicit_step_v1.py`
- `tools/run_core_v3_implicit_step.py`
- `tests/test_core_v3_implicit_step_v1.py`
